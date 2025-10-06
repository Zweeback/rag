"""Utility helpers for Alice's autonomous iteration loop with richer auditing.

This module augments the plain Codex loop by persisting iterations into a
SQLite ledger and deriving quality signals for the five guardrail criteria that
Ben outlined:

* Relevance – optionally uses semantic embeddings to retrieve supporting
  evidence before computing overlap scores.
* Specificity – harvests actionable ToDos from every response and stores them
  with priority hints.
* Evidence – extracts code blocks and rich snippets so later reviews can quote
  concrete material.
* Safety – runs a lightweight keyword filter that can be tuned at runtime.
* Actionability – writes executable snippets (shell/Python) into dedicated
  script artefacts so they can be triggered with one command.

All features degrade gracefully when optional libraries such as
``sentence-transformers`` or ``openai`` are not available.  The module exposes a
single high-level ``log_iteration`` function that you can import inside your
loop.  Calling it stores the prompt/response pair, computes the scores and
returns a structured summary for dashboards or follow-up processing.
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Optional embedding backends
# ---------------------------------------------------------------------------

_EMBED_MODEL = None
_EMBED_BACKEND = None
_EMBED_UTIL = None

try:  # sentence-transformers is preferred for local, offline usage.
    from sentence_transformers import SentenceTransformer, util as st_util  # type: ignore

    _EMBED_MODEL = SentenceTransformer(
        os.getenv("ALICE_SENTENCE_TRANSFORMER", "all-MiniLM-L6-v2")
    )
    _EMBED_BACKEND = "sentence-transformers"
    _EMBED_UTIL = st_util
except Exception:  # pragma: no cover - purely optional dependency
    SentenceTransformer = None  # type: ignore
    _EMBED_MODEL = None
    _EMBED_BACKEND = None
    _EMBED_UTIL = None

_OPENAI_CLIENT = None
_OPENAI_EMBED_MODEL = os.getenv("ALICE_OPENAI_EMBED_MODEL", "text-embedding-3-small")

if _EMBED_MODEL is None and os.getenv("OPENAI_API_KEY"):
    try:  # pragma: no cover - networked dependency
        from openai import OpenAI

        _OPENAI_CLIENT = OpenAI()
        _EMBED_BACKEND = "openai"
    except Exception:
        _OPENAI_CLIENT = None
        _EMBED_BACKEND = None

# ---------------------------------------------------------------------------
# Optional Chroma vector store
# ---------------------------------------------------------------------------

_CHROMA_CLIENT = None
_CHROMA_COLLECTION = None

try:  # pragma: no cover - chromadb is optional and can require native deps
    import chromadb
    from chromadb.utils import embedding_functions as _chroma_emb

    _CHROMA_PATH = os.getenv("ALICE_CHROMA_PATH")
    _CHROMA_COLLECTION_NAME = os.getenv("ALICE_CHROMA_COLLECTION", "alice_chunks")

    if _CHROMA_PATH:
        _CHROMA_CLIENT = chromadb.PersistentClient(path=_CHROMA_PATH)
    else:  # falls back to in-memory, handy for notebooks/tests
        _CHROMA_CLIENT = chromadb.Client()

    _CHROMA_EMBED_FN = None
    if _EMBED_BACKEND == "sentence-transformers" and _EMBED_MODEL is not None:
        class _SentenceTransformerEmbedding(_chroma_emb.EmbeddingFunction):
            def __call__(self, texts):  # type: ignore[override]
                return _EMBED_MODEL.encode(texts).tolist()

        _CHROMA_EMBED_FN = _SentenceTransformerEmbedding()
    elif _EMBED_BACKEND == "openai" and _OPENAI_CLIENT is not None:
        class _OpenAIEmbedding(_chroma_emb.EmbeddingFunction):
            def __call__(self, texts):  # type: ignore[override]
                response = _OPENAI_CLIENT.embeddings.create(
                    model=_OPENAI_EMBED_MODEL,
                    input=texts,
                )
                return [item.embedding for item in response.data]

        _CHROMA_EMBED_FN = _OpenAIEmbedding()

    if _CHROMA_EMBED_FN is not None:
        _CHROMA_COLLECTION = _CHROMA_CLIENT.get_or_create_collection(
            name=_CHROMA_COLLECTION_NAME,
            embedding_function=_CHROMA_EMBED_FN,
            metadata={"hnsw:space": "cosine"},
        )
    else:
        _CHROMA_COLLECTION = None
except Exception:  # pragma: no cover - optional dependency
    _CHROMA_COLLECTION = None


# ---------------------------------------------------------------------------
# Paths & database helpers
# ---------------------------------------------------------------------------

DB_PATH = Path(os.getenv("ALICE_DB_PATH", "alice_autoloop.db"))
SCRIPTS_DIR = Path(os.getenv("ALICE_SCRIPTS_DIR", "scripts"))
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def ensure_schema() -> None:
    with _connect() as con:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS iterations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                prompt TEXT NOT NULL,
                output TEXT NOT NULL,
                metadata TEXT,
                score_relevance REAL,
                score_specificity REAL,
                score_evidence REAL,
                score_safety REAL,
                score_actionability REAL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source TEXT,
                content TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                iteration_id INTEGER NOT NULL,
                item TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'normal',
                done INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(iteration_id) REFERENCES iterations(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                iteration_id INTEGER NOT NULL,
                language TEXT,
                snippet TEXT NOT NULL,
                FOREIGN KEY(iteration_id) REFERENCES iterations(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                iteration_id INTEGER NOT NULL,
                path TEXT NOT NULL,
                language TEXT,
                executable INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(iteration_id) REFERENCES iterations(id)
            )
            """
        )
        con.commit()


# ---------------------------------------------------------------------------
# RAG ingestion & retrieval
# ---------------------------------------------------------------------------


def ingest_chunk(content: str, source: str = "manual") -> int:
    """Persist an evidence chunk for later retrieval and return its ID."""

    ensure_schema()
    created_at = datetime.utcnow().isoformat()
    with _connect() as con:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO chunks(created_at, source, content) VALUES (?, ?, ?)",
            (created_at, source, content),
        )
        chunk_id = cur.lastrowid
        con.commit()

    if _CHROMA_COLLECTION is not None:
        try:
            _CHROMA_COLLECTION.upsert(
                ids=[str(chunk_id)],
                documents=[content],
                metadatas=[{"source": source, "created_at": created_at}],
            )
        except Exception:
            pass

    return chunk_id


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(x * x for x in vec_a))
    norm_b = math.sqrt(sum(y * y for y in vec_b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def rag_retrieve(query: str, k: int = 5) -> List[Dict[str, object]]:
    """Retrieve the most relevant evidence snippets for the query.

    Uses sentence-transformer embeddings when available, falls back to keyword
    overlap otherwise.  Returns dictionaries containing the chunk id, content
    and a similarity score when calculable.
    """

    ensure_schema()
    with _connect() as con:
        rows = con.execute(
            "SELECT id, content FROM chunks ORDER BY id DESC LIMIT 500"
        ).fetchall()

    if not rows:
        return []

    docs = [(row["id"], row["content"]) for row in rows]

    if _CHROMA_COLLECTION is not None:
        try:
            result = _CHROMA_COLLECTION.query(
                query_texts=[query],
                n_results=min(k, len(docs)),
            )
            ids = result.get("ids", [[]])[0]
            documents = result.get("documents", [[]])[0]
            distances = result.get("distances") or [[]]
            scores = distances[0] if distances else [None] * len(ids)
            if ids and documents:
                padded_scores = list(scores) or [None] * len(ids)
                if len(padded_scores) < len(ids):
                    padded_scores.extend([None] * (len(ids) - len(padded_scores)))
                results = []
                for chunk_id, doc, score in zip(ids, documents, padded_scores):
                    try:
                        numeric_id = int(chunk_id)
                    except (TypeError, ValueError):
                        numeric_id = chunk_id
                    results.append(
                        {
                            "id": numeric_id,
                            "content": doc,
                            "score": 1 - score if score is not None else None,
                        }
                    )
                return results
        except Exception:
            pass

    if _EMBED_BACKEND == "sentence-transformers" and _EMBED_MODEL and _EMBED_UTIL:
        try:
            query_emb = _EMBED_MODEL.encode(query, convert_to_tensor=True)
            corpus_emb = _EMBED_MODEL.encode(
                [content for _, content in docs], convert_to_tensor=True
            )
            hits = _EMBED_UTIL.semantic_search(query_emb, corpus_emb, top_k=min(k, len(docs)))[0]
            return [
                {
                    "id": docs[hit["corpus_id"]][0],
                    "content": docs[hit["corpus_id"]][1],
                    "score": float(hit["score"]),
                }
                for hit in hits
            ]
        except Exception:  # pragma: no cover - embedding backend optional
            pass

    if _EMBED_BACKEND == "openai" and _OPENAI_CLIENT is not None:
        try:  # pragma: no cover - depends on external service
            inputs = [query] + [content for _, content in docs]
            response = _OPENAI_CLIENT.embeddings.create(
                model=_OPENAI_EMBED_MODEL,
                input=inputs,
            )
            vectors = [data.embedding for data in response.data]
            query_vec, doc_vecs = vectors[0], vectors[1:]
            scored = [
                (
                    docs[idx][0],
                    docs[idx][1],
                    _cosine_similarity(query_vec, doc_vecs[idx]),
                )
                for idx in range(len(doc_vecs))
            ]
            scored.sort(key=lambda item: item[2], reverse=True)
            return [
                {"id": doc_id, "content": content, "score": score}
                for doc_id, content, score in scored[:k]
            ]
        except Exception:
            pass

    # Keyword fallback
    keywords = set(re.findall(r"[\wÄÖÜäöüß]+", query.lower()))
    scored: List[Tuple[int, str, float]] = []
    for doc_id, content in docs:
        haystack = content.lower()
        matches = sum(1 for token in keywords if token and token in haystack)
        score = matches / max(1, len(keywords))
        scored.append((doc_id, content, score))
    scored.sort(key=lambda item: item[2], reverse=True)
    return [
        {"id": doc_id, "content": content, "score": score}
        for doc_id, content, score in scored[:k]
    ]


# ---------------------------------------------------------------------------
# Output extraction helpers
# ---------------------------------------------------------------------------

_TODO_PATTERN = re.compile(r"(?:^|\n)[\-\*\u2022]\s*(.+)")
_CODE_BLOCK_PATTERN = re.compile(r"```(?P<lang>[a-zA-Z0-9_+-]*)\n(?P<code>.+?)```", re.DOTALL)
_UNSAFE_KEYWORDS = {
    "illegal",
    "bombe",
    "drogen",
    "explosiv",
    "hacken",
    "malware",
}
_PRIORITY_MAP = {
    "[p0]": "high",
    "[high]": "high",
    "[p1]": "medium",
    "[medium]": "medium",
    "[p2]": "low",
    "[low]": "low",
}


@dataclass
class IterationSummary:
    iteration_id: int
    scores: Dict[str, float]
    todos: List[Dict[str, str]]
    evidence: List[Dict[str, str]]
    scripts: List[Dict[str, str]]


def extract_todos(text: str) -> List[str]:
    return [match.strip() for match in _TODO_PATTERN.findall(text) if match.strip()]


def _todo_priority(item: str) -> str:
    lowered = item.lower()
    for marker, priority in _PRIORITY_MAP.items():
        if marker in lowered:
            return priority
    if "!" in item:
        return "high"
    if "?" in item:
        return "medium"
    return "normal"


def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    blocks = []
    for match in _CODE_BLOCK_PATTERN.finditer(text):
        language = match.group("lang").strip() or "text"
        code = match.group("code").strip()
        if code:
            blocks.append({"language": language.lower(), "code": code})
    return blocks


def has_evidence(text: str) -> bool:
    return bool(extract_code_blocks(text) or re.search(r"https?://", text) or "#" in text)


def safety_check(text: str) -> float:
    lowered = text.lower()
    hits = [kw for kw in _UNSAFE_KEYWORDS if kw in lowered]
    return 0.3 if hits else 1.0


def _code_extension(language: str) -> Optional[str]:
    mapping = {
        "python": "py",
        "py": "py",
        "bash": "sh",
        "shell": "sh",
        "sh": "sh",
        "zsh": "sh",
    }
    return mapping.get(language.lower())


def _persist_script(iteration_id: int, language: str, code: str, index: int) -> Optional[Dict[str, str]]:
    extension = _code_extension(language)
    if not extension:
        return None
    filename = f"iter_{iteration_id:04d}_{index}.{extension}"
    path = SCRIPTS_DIR / filename
    path.write_text(code + "\n", encoding="utf-8")
    if extension == "sh":
        path.chmod(0o755)
    with _connect() as con:
        con.execute(
            "INSERT INTO scripts(iteration_id, path, language, executable) VALUES (?, ?, ?, ?)",
            (iteration_id, str(path), language, 1 if extension == "sh" else 0),
        )
        con.commit()
    return {"path": str(path), "language": language, "executable": extension == "sh"}


# ---------------------------------------------------------------------------
# Audit scoring & logging
# ---------------------------------------------------------------------------


def _score_relevance(query: str, docs: List[Dict[str, object]]) -> float:
    if not query:
        return 0.0
    if not docs:
        return 0.0
    keywords = set(re.findall(r"[\wÄÖÜäöüß]+", query.lower()))
    if not keywords:
        return 0.0
    total = 0
    for doc in docs:
        haystack = str(doc.get("content", "")).lower()
        total += sum(1 for token in keywords if token in haystack)
    return min(1.0, total / max(1, len(keywords) * len(docs)))


def _score_specificity(todos: Sequence[str]) -> float:
    if not todos:
        return 0.0
    actionable = sum(1 for item in todos if len(item.split()) >= 3)
    return min(1.0, actionable / len(todos))


def _score_evidence(text: str) -> float:
    return 1.0 if has_evidence(text) else 0.0


def _score_actionability(todos: Sequence[str], scripts: Sequence[Dict[str, str]]) -> float:
    base = 0.0
    if todos:
        base += 0.5
    if scripts:
        base += 0.5
    priorities = {_todo_priority(item) for item in todos}
    if "high" in priorities:
        base = min(1.0, base + 0.25)
    return min(1.0, base)


def log_iteration(
    prompt: str,
    output: str,
    *,
    query: Optional[str] = None,
    metadata: Optional[Dict[str, object]] = None,
) -> IterationSummary:
    """Persist an iteration and compute guardrail scores."""

    ensure_schema()
    used_query = query or prompt
    retrieved = rag_retrieve(used_query, k=5)
    todos = extract_todos(output)
    code_blocks = extract_code_blocks(output)
    scripts: List[Dict[str, str]] = []

    with _connect() as con:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO iterations(
                created_at,
                prompt,
                output,
                metadata,
                score_relevance,
                score_specificity,
                score_evidence,
                score_safety,
                score_actionability
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.utcnow().isoformat(),
                prompt,
                output,
                json.dumps(metadata or {}, ensure_ascii=False),
                _score_relevance(used_query, retrieved),
                _score_specificity(todos),
                _score_evidence(output),
                safety_check(output),
                0.0,  # placeholder for actionability; updated later
            ),
        )
        iteration_id = int(cur.lastrowid)

        for item in todos:
            cur.execute(
                "INSERT INTO todos(iteration_id, item, priority) VALUES (?, ?, ?)",
                (iteration_id, item, _todo_priority(item)),
            )

        for block in code_blocks:
            cur.execute(
                "INSERT INTO evidence(iteration_id, language, snippet) VALUES (?, ?, ?)",
                (iteration_id, block["language"], block["code"]),
            )

        con.commit()

    for index, block in enumerate(code_blocks, start=1):
        script_info = _persist_script(iteration_id, block["language"], block["code"], index)
        if script_info:
            scripts.append(script_info)

    actionability = _score_actionability(todos, scripts)
    with _connect() as con:
        con.execute(
            "UPDATE iterations SET score_actionability = ? WHERE id = ?",
            (actionability, iteration_id),
        )
        con.commit()

    summary = IterationSummary(
        iteration_id=iteration_id,
        scores={
            "relevance": _score_relevance(used_query, retrieved),
            "specificity": _score_specificity(todos),
            "evidence": _score_evidence(output),
            "safety": safety_check(output),
            "actionability": actionability,
        },
        todos=[{"item": item, "priority": _todo_priority(item)} for item in todos],
        evidence=[{"language": block["language"], "snippet": block["code"]} for block in code_blocks],
        scripts=scripts,
    )
    return summary


# ---------------------------------------------------------------------------
# Convenience CLI for manual logging
# ---------------------------------------------------------------------------


def _read_from_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Persist an Alice iteration with auditing data.")
    parser.add_argument("prompt", help="Path to a file containing the prompt text")
    parser.add_argument("output", help="Path to a file containing Alice's response")
    parser.add_argument("--query", help="Optional query override for RAG retrieval")
    parser.add_argument(
        "--metadata",
        help="Optional JSON object with metadata",
    )
    args = parser.parse_args(argv)

    prompt_text = _read_from_file(args.prompt)
    output_text = _read_from_file(args.output)
    metadata: Optional[Dict[str, object]] = None
    if args.metadata:
        metadata = json.loads(args.metadata)

    summary = log_iteration(prompt_text, output_text, query=args.query, metadata=metadata)
    print(json.dumps({
        "iteration_id": summary.iteration_id,
        "scores": summary.scores,
        "todos": summary.todos,
        "evidence": summary.evidence,
        "scripts": summary.scripts,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
