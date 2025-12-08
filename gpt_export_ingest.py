"""Convert ChatGPT export JSON files into RAG chunks for the Alice ledger.

This script reads one or multiple ChatGPT export JSON files (for example the
``conversations.json`` you get from a data export) and writes compact text
chunks into the ``alice_autoloop`` evidence store via ``ingest_chunk``. Each
chunk preserves role labels and timestamps so you can later search and retrieve
past prompts and replies through the existing RAG retrieval helpers.

Usage example:
    python gpt_export_ingest.py /path/to/export --source gdrive --chunk-size 1200
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from alice_autoloop import ingest_chunk

Conversation = Dict[str, object]
Message = Tuple[Optional[float], str, str]


def _load_conversations(path: Path) -> List[Conversation]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if isinstance(data, dict):
        candidates: Sequence[object] = []
        if isinstance(data.get("conversations"), list):
            candidates = data["conversations"]
        elif isinstance(data.get("items"), list):
            candidates = data["items"]
        return [item for item in candidates if isinstance(item, dict)]

    return []


def _to_datetime(timestamp: Optional[float]) -> Optional[str]:
    if not timestamp:
        return None
    try:
        return datetime.fromtimestamp(float(timestamp)).isoformat()
    except Exception:
        return None


def _collect_messages(conversation: Conversation) -> List[Message]:
    messages: List[Message] = []

    mapping = conversation.get("mapping")
    if isinstance(mapping, dict):
        for node in mapping.values():
            if not isinstance(node, dict):
                continue
            message = node.get("message")
            if not isinstance(message, dict):
                continue
            author = message.get("author")
            role = author.get("role") if isinstance(author, dict) else None
            role_label = str(role or "unknown")
            content_obj = message.get("content")
            text_parts: List[str] = []
            if isinstance(content_obj, dict):
                parts = content_obj.get("parts")
                if isinstance(parts, list):
                    text_parts = [str(part) for part in parts if str(part).strip()]
            elif isinstance(content_obj, str):
                text_parts = [content_obj]
            content = "\n".join(text_parts).strip()
            if not content:
                continue
            created = message.get("create_time") or node.get("create_time")
            created_ts = float(created) if isinstance(created, (int, float, str)) else None
            messages.append((created_ts, role_label, content))

    if not messages:
        plain_messages = conversation.get("messages")
        if isinstance(plain_messages, list):
            for msg in plain_messages:
                if not isinstance(msg, dict):
                    continue
                role_label = str(msg.get("role") or msg.get("author") or "unknown")
                content = str(msg.get("content") or "").strip()
                if not content:
                    continue
                created_ts: Optional[float] = None
                created = msg.get("create_time") or msg.get("timestamp")
                if isinstance(created, (int, float, str)):
                    try:
                        created_ts = float(created)
                    except Exception:
                        created_ts = None
                messages.append((created_ts, role_label, content))

    messages.sort(key=lambda item: (item[0] is None, item[0]))
    return messages


def _format_conversation(conversation: Conversation) -> str:
    title = str(conversation.get("title") or conversation.get("name") or "Ohne Titel")
    created_at = _to_datetime(conversation.get("create_time"))
    header_parts = [f"# Chat: {title}"]
    if created_at:
        header_parts.append(f"(erstellt: {created_at})")
    lines = [" ".join(header_parts).strip(), ""]

    for created_ts, role, content in _collect_messages(conversation):
        stamp = _to_datetime(created_ts)
        prefix = f"[{role}]"
        if stamp:
            prefix = f"[{role} @ {stamp}]"
        lines.append(f"{prefix}\n{content}\n")

    return "\n".join(lines).strip()


def _chunk_text(text: str, size: int, overlap: int) -> Iterable[str]:
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        yield text[start:end].strip()
        if end == len(text):
            break
        start = max(0, end - overlap)


def ingest_conversation(
    conversation: Conversation, source_prefix: str, chunk_size: int, overlap: int
) -> int:
    transcript = _format_conversation(conversation)
    if not transcript:
        return 0

    title = str(conversation.get("title") or conversation.get("name") or "conversation")
    chunks = list(_chunk_text(transcript, size=chunk_size, overlap=overlap))
    for chunk in chunks:
        if not chunk:
            continue
        ingest_chunk(chunk, source=f"{source_prefix}:{title}")
    return len(chunks)


def ingest_exports(paths: Sequence[Path], source: str, chunk_size: int, overlap: int) -> int:
    total_chunks = 0
    for path in paths:
        conversations = _load_conversations(path)
        for conversation in conversations:
            total_chunks += ingest_conversation(
                conversation, source_prefix=f"{source}:{path.stem}", chunk_size=chunk_size, overlap=overlap
            )
    return total_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest ChatGPT export JSON into the RAG store")
    parser.add_argument("path", type=Path, help="Path to a ChatGPT export JSON file or directory")
    parser.add_argument(
        "--source",
        default="gpt-export",
        help="Label stored alongside the chunks (e.g. gdrive, local, backup)",
    )
    parser.add_argument("--chunk-size", type=int, default=1200, help="Max characters per chunk")
    parser.add_argument("--overlap", type=int, default=200, help="Character overlap between chunks")
    args = parser.parse_args()

    if args.path.is_dir():
        targets = sorted(p for p in args.path.glob("*.json") if p.is_file())
    else:
        targets = [args.path]

    if not targets:
        raise SystemExit(f"Keine JSON-Dateien gefunden unter {args.path}")

    total = ingest_exports(
        targets, source=args.source, chunk_size=args.chunk_size, overlap=args.overlap
    )
    print(f"Insgesamt {total} Chunks aus {len(targets)} Datei(en) übernommen.")


if __name__ == "__main__":
    main()
