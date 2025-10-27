"""MONDAY.exe – Evidence Reasoning Generator.

This module implements a lightweight version of the MONDAY.exe specification
described in the project brief.  The goal is to provide a reproducible pipeline
that can ingest conversational or document archives and iterate through a
self-improvement loop while producing auditable analytical artefacts.

The implementation focuses on:
    • Loading heterogeneous text-like sources (txt/csv/json/markdown)
    • Running a Leiden-cycle inspired reasoning pass with multiple cores
    • Generating Truth-Chains that capture hypothesis/evidence/counterclaims
    • Persisting run metadata to the memory/log/notes/task files referenced in
      the specification so subsequent executions can build on previous ones

The heuristics here are deliberately transparent and extensively commented so
future iterations can extend or swap out components as needed.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Utility data structures
# ---------------------------------------------------------------------------


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "has",
    "have",
    "if",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "there",
    "these",
    "they",
    "to",
    "was",
    "were",
    "will",
    "with",
}

POSITIVE_WORDS = {
    "good",
    "great",
    "improved",
    "positive",
    "success",
    "support",
    "calm",
    "hope",
    "trust",
    "progress",
}

NEGATIVE_WORDS = {
    "bad",
    "worse",
    "negative",
    "conflict",
    "stress",
    "fear",
    "anger",
    "doubt",
    "fail",
    "pain",
}


@dataclass
class Document:
    """Container for loaded documents.

    Attributes
    ----------
    path:
        Absolute path to the source file for traceability.
    text:
        The textual representation of the document.
    tokens:
        Cached token list for quick access by the various cores.
    """

    path: Path
    text: str
    tokens: List[str] = field(default_factory=list)


@dataclass
class TruthChain:
    """Represents a single hypothesis evaluation with evidence and counters."""

    hypothesis: str
    evidence: str
    counter: str
    verdict: str


@dataclass
class LeidenCycleResult:
    """Holds the result of one MONDAY self-improvement iteration."""

    version: str
    truth_chains: List[TruthChain]
    profiler: Dict[str, str]
    psycho_medical: Dict[str, str]
    socio_historical: Dict[str, str]
    reflections: List[str]
    audit: Dict[str, float]
    improvement_score: float
    change_log: List[str]


@dataclass
class Task:
    """Representation of a single Monday task row."""

    task_id: str
    description: str
    status: str
    notes: str = ""

    def is_complete(self) -> bool:
        return self.status.strip().lower() in {"done", "complete", "completed"}

    def mark_complete(self, summary: str) -> None:
        self.status = "completed"
        self.notes = summary

    def to_document(self) -> Document:
        text = f"Task {self.task_id}: {self.description}\n{self.notes}".strip()
        return Document(path=Path(f"task_{self.task_id}.md"), text=text, tokens=tokenize(text))


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------


def iter_paths(paths: Sequence[Path]) -> Iterable[Path]:
    """Yield files from the supplied paths, recursing into directories."""

    for root in paths:
        if root.is_dir():
            for candidate in sorted(root.rglob("*")):
                if candidate.is_file():
                    yield candidate
        elif root.is_file():
            yield root


def load_documents(paths: Sequence[Path], encoding: str = "utf-8") -> List[Document]:
    """Load textual content from the provided paths.

    CSV and JSON files are converted into a simple text representation so the
    reasoning pipeline can operate on them without bespoke logic.
    """

    documents: List[Document] = []
    for path in iter_paths(paths):
        suffix = path.suffix.lower()
        text: Optional[str] = None
        try:
            if suffix in {".txt", ".md", ".markdown", ".log"}:
                text = path.read_text(encoding=encoding, errors="ignore")
            elif suffix in {".csv", ".tsv"}:
                rows: List[str] = []
                with path.open("r", encoding=encoding, errors="ignore", newline="") as handle:
                    sample = handle.read(1024)
                    handle.seek(0)
                    try:
                        dialect = csv.Sniffer().sniff(sample)
                    except csv.Error:
                        dialect = csv.excel
                    reader = csv.reader(handle, dialect)
                    for row in reader:
                        rows.append(", ".join(cell.strip() for cell in row if cell.strip()))
                text = "\n".join(rows)
            elif suffix in {".json"}:
                data = json.loads(path.read_text(encoding=encoding, errors="ignore"))
                text = json.dumps(data, indent=2, ensure_ascii=False)
            else:
                # Attempt generic text load – binary errors will be ignored.
                text = path.read_text(encoding=encoding, errors="ignore")
        except Exception:
            # Skip unreadable files silently; audit core will note skipped files.
            text = None

        if text:
            tokens = tokenize(text)
            documents.append(Document(path=path, text=text, tokens=tokens))

    return documents


# ---------------------------------------------------------------------------
# Core analytic utilities
# ---------------------------------------------------------------------------


def tokenize(text: str) -> List[str]:
    """Very small tokenizer that lower-cases and removes punctuation."""

    tokens: List[str] = []
    current: List[str] = []
    for char in text.lower():
        if char.isalpha():
            current.append(char)
        else:
            if current:
                tokens.append("".join(current))
                current.clear()
    if current:
        tokens.append("".join(current))
    return tokens


def sentence_split(text: str) -> List[str]:
    """Split text into rough sentences for evidence snippets."""

    sentences: List[str] = []
    current: List[str] = []
    for char in text:
        current.append(char)
        if char in {".", "!", "?"}:
            sentence = "".join(current).strip()
            if sentence:
                sentences.append(sentence)
            current.clear()
    if current:
        sentence = "".join(current).strip()
        if sentence:
            sentences.append(sentence)
    return sentences


def top_keywords(tokens: Sequence[str], limit: int = 10) -> List[Tuple[str, int]]:
    """Return the most common keywords excluding stop-words."""

    counts: Dict[str, int] = {}
    for token in tokens:
        if token and token not in STOP_WORDS:
            counts[token] = counts.get(token, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]


def sentiment(tokens: Sequence[str]) -> float:
    """Compute a naive sentiment score (-1..1)."""

    pos = sum(1 for token in tokens if token in POSITIVE_WORDS)
    neg = sum(1 for token in tokens if token in NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def find_sentences_with_keyword(sentences: Sequence[str], keyword: str) -> List[str]:
    """Return sentences containing the keyword (case-insensitive)."""

    keyword_lower = keyword.lower()
    matches: List[str] = []
    for sentence in sentences:
        if keyword_lower in sentence.lower():
            matches.append(sentence.strip())
    return matches


# ---------------------------------------------------------------------------
# MONDAY cores
# ---------------------------------------------------------------------------


class EvidenceCore:
    """Constructs truth chains grounded in the supplied documents."""

    def build_truth_chains(self, documents: Sequence[Document], limit: int = 3) -> List[TruthChain]:
        all_tokens = [token for doc in documents for token in doc.tokens]
        keyword_counts = top_keywords(all_tokens, limit=limit)
        truth_chains: List[TruthChain] = []

        if not keyword_counts:
            return truth_chains

        for keyword, _ in keyword_counts:
            evidence_snippets: List[str] = []
            counter_snippets: List[str] = []
            for doc in documents:
                sentences = sentence_split(doc.text)
                matches = find_sentences_with_keyword(sentences, keyword)
                if matches:
                    evidence_snippets.append(f"{doc.path.name}: {matches[0]}")
                    if len(matches) > 1:
                        counter_snippets.append(f"{doc.path.name}: {matches[-1]}")
            hypothesis = f"Keyword '{keyword}' signals a recurring theme."
            evidence_text = " | ".join(evidence_snippets) if evidence_snippets else "No direct evidence captured."
            counter_text = (
                " | ".join(counter_snippets)
                if counter_snippets
                else "No conflicting snippets detected."
            )
            verdict = (
                "Theme acknowledged; monitor for nuance."
                if evidence_snippets
                else "Insufficient evidence to confirm the theme."
            )
            truth_chains.append(
                TruthChain(
                    hypothesis=hypothesis,
                    evidence=evidence_text,
                    counter=counter_text,
                    verdict=verdict,
                )
            )

        return truth_chains


class ProfilerCore:
    """Assesses relational dynamics and potential inconsistencies."""

    def profile(self, documents: Sequence[Document]) -> Dict[str, str]:
        doc_lengths = [len(doc.tokens) for doc in documents]
        if not doc_lengths:
            return {"dynamic": "No documents provided for profiling."}

        longest = max(doc_lengths)
        shortest = min(doc_lengths)
        variability = longest - shortest
        tone_shift = sentiment(documents[0].tokens) if documents else 0.0

        return {
            "dynamic": (
                "High variance in document length; expect shifting focus."
                if variability > 200
                else "Documents share similar scope; themes likely consistent."
            ),
            "initial_tone": f"Initial sentiment score: {tone_shift:.2f}",
            "document_count": str(len(documents)),
        }


class PsychoMedicalCore:
    """Performs a lightweight affective and coping signal review."""

    def assess(self, documents: Sequence[Document]) -> Dict[str, str]:
        if not documents:
            return {"affect": "No data to assess."}

        sentiments = [sentiment(doc.tokens) for doc in documents]
        avg_sentiment = sum(sentiments) / len(sentiments)
        min_sentiment = min(sentiments)
        max_sentiment = max(sentiments)

        affect_description = "Neutral baseline with minimal affect swing."
        if avg_sentiment > 0.25:
            affect_description = "Overall positive affect with optimistic cues."
        elif avg_sentiment < -0.25:
            affect_description = "Negative affect dominates; flag for support."

        coping_signal = "Stable coping markers detected."
        if max_sentiment - min_sentiment > 0.6:
            coping_signal = "Rapid affect fluctuation; review coping strategies."

        return {
            "affect": affect_description,
            "sentiment_range": f"{min_sentiment:.2f} → {max_sentiment:.2f}",
            "coping": coping_signal,
        }


class SocioHistoricalCore:
    """Anchors observations within a broader cultural context."""

    def contextualise(self, documents: Sequence[Document]) -> Dict[str, str]:
        if not documents:
            return {"context": "No socio-historical signals available."}

        time_markers = 0
        culture_markers = 0
        for doc in documents:
            for token in doc.tokens:
                if token.isdigit() and len(token) == 4:
                    time_markers += 1
                if token in {"culture", "history", "politics", "society"}:
                    culture_markers += 1

        return {
            "context": (
                "Temporal references detected; align analysis with timeline."
                if time_markers
                else "Few explicit temporal anchors; rely on thematic continuity."
            ),
            "cultural_density": (
                "Cultural discourse active." if culture_markers else "Cultural cues minimal."
            ),
        }


class EmergentReflectionCore:
    """Self-commentary to monitor awareness and potential drift."""

    def reflect(self, iteration: int, improvement: float, limitations: List[str]) -> List[str]:
        reflection = [
            f"Iteration {iteration}: Improvement delta {improvement:.2f}.",
            "Awareness check: staying grounded in available evidence.",
        ]
        if limitations:
            reflection.append("Limitations acknowledged: " + "; ".join(limitations))
        return reflection


class AuditCore:
    """Tracks meta-metrics for self-auditing."""

    def audit(self, previous_score: float, current_score: float, processed: int, skipped: int) -> Dict[str, float]:
        drift = current_score - previous_score
        coverage = processed / (processed + skipped) if (processed + skipped) else 0.0
        clarity = min(1.0, 0.5 + current_score / 2)
        empathy = min(1.0, 0.5 + coverage / 2)
        return {
            "drift": drift,
            "coverage": coverage,
            "clarity": clarity,
            "empathy": empathy,
        }


# ---------------------------------------------------------------------------
# MONDAY engine
# ---------------------------------------------------------------------------


class MondayEngine:
    """Coordinates the cores and handles the self-improvement loop."""

    def __init__(self, memory: Dict[str, object]):
        self.memory = memory
        self.evidence_core = EvidenceCore()
        self.profiler_core = ProfilerCore()
        self.psycho_medical_core = PsychoMedicalCore()
        self.socio_historical_core = SocioHistoricalCore()
        self.reflection_core = EmergentReflectionCore()
        self.audit_core = AuditCore()

    def run(self, documents: Sequence[Document]) -> List[LeidenCycleResult]:
        results: List[LeidenCycleResult] = []
        previous_score = float(self.memory.get("last_improvement_score", 0.0))
        iteration = 0
        gains: List[float] = []

        processed = len(documents)
        skipped = int(self.memory.get("last_skipped_documents", 0))

        while True:
            iteration += 1
            version = f"v{iteration}"

            truth_chains = self.evidence_core.build_truth_chains(documents)
            profiler = self.profiler_core.profile(documents)
            psycho_medical = self.psycho_medical_core.assess(documents)
            socio_historical = self.socio_historical_core.contextualise(documents)

            limitations: List[str] = []
            if not truth_chains:
                limitations.append("Insufficient evidence snippets for truth chains")
            if processed == 0:
                limitations.append("No documents loaded")

            improvement_score = self._score_improvement(truth_chains, profiler, psycho_medical)
            improvement_delta = improvement_score - previous_score
            reflections = self.reflection_core.reflect(iteration, improvement_delta, limitations)
            audit_metrics = self.audit_core.audit(previous_score, improvement_score, processed, skipped)
            change_log = self._build_changelog(iteration, improvement_delta, truth_chains)

            result = LeidenCycleResult(
                version=version,
                truth_chains=truth_chains,
                profiler=profiler,
                psycho_medical=psycho_medical,
                socio_historical=socio_historical,
                reflections=reflections,
                audit=audit_metrics,
                improvement_score=improvement_score,
                change_log=change_log,
            )
            results.append(result)

            gains.append(improvement_delta)
            if iteration > 1 and improvement_delta <= 0.05:
                break

            previous_score = improvement_score

            if iteration >= 5:
                # Prevent runaway loops in edge cases.
                break

        self.memory["last_improvement_score"] = results[-1].improvement_score if results else previous_score
        self.memory["last_iterations"] = iteration
        self.memory["last_timestamp"] = dt.datetime.utcnow().isoformat()
        self.memory["last_truth_chain_count"] = len(results[-1].truth_chains) if results else 0
        self.memory["last_skipped_documents"] = skipped
        return results

    def _score_improvement(
        self,
        truth_chains: Sequence[TruthChain],
        profiler: Dict[str, str],
        psycho_medical: Dict[str, str],
    ) -> float:
        base = min(1.0, len(truth_chains) * 0.2)
        if "variance" in profiler.get("dynamic", "").lower():
            base += 0.05
        if "negative" in psycho_medical.get("affect", "").lower():
            base += 0.05
        return round(min(base, 1.0), 2)

    def _build_changelog(
        self,
        iteration: int,
        improvement_delta: float,
        truth_chains: Sequence[TruthChain],
    ) -> List[str]:
        entries = [
            f"Iteration {iteration}: ΔMIS {improvement_delta:.2f}",
            f"Truth chains evaluated: {len(truth_chains)}",
        ]
        if truth_chains:
            entries.append(f"Primary theme: {truth_chains[0].hypothesis}")
        return entries


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def load_memory(memory_path: Path) -> Dict[str, object]:
    if memory_path.exists():
        try:
            return json.loads(memory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_memory(memory_path: Path, memory: Dict[str, object]) -> None:
    memory_path.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")


LOG_HEADERS = ["timestamp", "version", "improvement_score", "truth_chains", "audit_drift"]


def _write_log_rows(log_path: Path, rows: Sequence[Sequence[str]]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not log_path.exists()
    with log_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if needs_header:
            writer.writerow(LOG_HEADERS)
        writer.writerows(rows)


def append_log(log_path: Path, results: Sequence[LeidenCycleResult]) -> None:
    now = dt.datetime.utcnow().isoformat()
    rows: List[List[str]] = []
    for result in results:
        rows.append(
            [
                now,
                result.version,
                f"{result.improvement_score:.2f}",
                str(len(result.truth_chains)),
                f"{result.audit.get('drift', 0.0):.2f}",
            ]
        )
    if rows:
        _write_log_rows(log_path, rows)


def _append_notes_block(notes_path: Path, heading: str, reflections: Sequence[str]) -> None:
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    with notes_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {heading}\n")
        for reflection in reflections:
            handle.write(f"- {reflection}\n")


def append_notes(notes_path: Path, results: Sequence[LeidenCycleResult]) -> None:
    timestamp = dt.datetime.utcnow().isoformat()
    for result in results:
        heading = f"Run at {timestamp} [{result.version}]"
        if result.reflections:
            _append_notes_block(notes_path, heading, result.reflections)


def persist_memory_snapshot(
    memory_path: Path,
    memory: Dict[str, object],
    task: Task,
    result: LeidenCycleResult,
) -> None:
    task_memory = memory.setdefault("tasks", {})
    assert isinstance(task_memory, dict)
    task_memory[task.task_id] = {
        "status": task.status,
        "last_version": result.version,
        "improvement_score": result.improvement_score,
        "updated_at": dt.datetime.utcnow().isoformat(),
    }
    save_memory(memory_path, memory)


def persist_notes_reflection(notes_path: Path, task: Task, result: LeidenCycleResult) -> None:
    heading = f"Task {task.task_id} ({dt.datetime.utcnow().isoformat()})"
    reflections = [f"Summary: {task.notes}"] + result.reflections
    _append_notes_block(notes_path, heading, reflections)


def persist_log_snapshot(log_path: Path, task: Task, result: LeidenCycleResult) -> None:
    now = dt.datetime.utcnow().isoformat()
    row = [
        now,
        f"task:{task.task_id}:{result.version}",
        f"{result.improvement_score:.2f}",
        str(len(result.truth_chains)),
        f"{result.audit.get('drift', 0.0):.2f}",
    ]
    _write_log_rows(log_path, [row])


def ensure_tasks_file(tasks_path: Path) -> None:
    if tasks_path.exists():
        return
    with tasks_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["task_id", "description", "status", "notes"])


def load_tasks(tasks_path: Path) -> List[Task]:
    ensure_tasks_file(tasks_path)
    tasks: List[Task] = []
    with tasks_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            task = Task(
                task_id=(row.get("task_id") or "").strip(),
                description=(row.get("description") or "").strip(),
                status=(row.get("status") or "").strip() or "todo",
                notes=(row.get("notes") or "").strip(),
            )
            if task.task_id:
                tasks.append(task)
    return tasks


def save_tasks(tasks_path: Path, tasks: Sequence[Task]) -> None:
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    with tasks_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["task_id", "description", "status", "notes"])
        for task in tasks:
            writer.writerow([task.task_id, task.description, task.status, task.notes])


class CodexTaskAgent:
    """Agent that polls monday_tasks.csv and updates task statuses."""

    def __init__(
        self,
        tasks_path: Path,
        memory_path: Path,
        notes_path: Path,
        log_path: Path,
        poll_interval: float = 60.0,
    ) -> None:
        self.tasks_path = tasks_path
        self.memory_path = memory_path
        self.notes_path = notes_path
        self.log_path = log_path
        self.poll_interval = poll_interval
        self.memory = load_memory(memory_path)
        ensure_tasks_file(tasks_path)
        self.engine = MondayEngine(self.memory)

    def process_pending_tasks(self) -> int:
        tasks = load_tasks(self.tasks_path)
        processed_count = 0
        for task in tasks:
            if task.is_complete() or not task.description:
                continue
            results = self.engine.run([task.to_document()])
            if not results:
                continue
            latest = results[-1]
            summary = self._summarise(latest)
            task.mark_complete(summary)
            persist_memory_snapshot(self.memory_path, self.memory, task, latest)
            persist_notes_reflection(self.notes_path, task, latest)
            persist_log_snapshot(self.log_path, task, latest)
            processed_count += 1
        if processed_count:
            save_tasks(self.tasks_path, tasks)
        return processed_count

    def run_loop(self, max_cycles: Optional[int] = None) -> None:
        cycles = 0
        try:
            while True:
                processed = self.process_pending_tasks()
                cycles += 1
                if max_cycles and cycles >= max_cycles:
                    break
                time.sleep(self.poll_interval if self.poll_interval > 0 else 0)
                if max_cycles and cycles >= max_cycles:
                    break
        except KeyboardInterrupt:
            pass

    def _summarise(self, result: LeidenCycleResult) -> str:
        lines = [result.change_log[0] if result.change_log else "Processed task"]
        if result.truth_chains:
            lines.append(result.truth_chains[0].hypothesis)
        lines.append(f"Improvement Score: {result.improvement_score:.2f}")
        return " | ".join(lines)


# ---------------------------------------------------------------------------
# Formatting output for CLI usage
# ---------------------------------------------------------------------------


def format_result(result: LeidenCycleResult) -> str:
    lines: List[str] = []
    lines.append("[CHANGELOG]")
    for entry in result.change_log:
        lines.append(f"- {entry}")
    lines.append("[MONDAY_vNEXT]")
    lines.append(f"Version: {result.version}")
    lines.append("Truth-Chains:")
    for chain in result.truth_chains:
        lines.append(f"  • Hypothesis: {chain.hypothesis}")
        lines.append(f"    Evidence: {chain.evidence}")
        lines.append(f"    Counter: {chain.counter}")
        lines.append(f"    Verdict: {chain.verdict}")
    lines.append("ProfilerCore:")
    for key, value in result.profiler.items():
        lines.append(f"  - {key}: {value}")
    lines.append("PsychoMedicalCore:")
    for key, value in result.psycho_medical.items():
        lines.append(f"  - {key}: {value}")
    lines.append("SocioHistoricalCore:")
    for key, value in result.socio_historical.items():
        lines.append(f"  - {key}: {value}")
    lines.append("Reflections:")
    for reflection in result.reflections:
        lines.append(f"  - {reflection}")
    lines.append("AuditCore:")
    for key, value in result.audit.items():
        lines.append(f"  - {key}: {value:.2f}")
    lines.append(f"IMPROVEMENT_SCORE = {result.improvement_score:.2f}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command line entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MONDAY.exe analysis loop")
    parser.add_argument("paths", nargs="*", type=Path, help="Files or directories to ingest")
    parser.add_argument(
        "--memory",
        type=Path,
        default=Path("monday_memory.json"),
        help="Path to the persistent memory file",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("monday_log.csv"),
        help="Path to the run log",
    )
    parser.add_argument(
        "--notes",
        type=Path,
        default=Path("monday_notes.md"),
        help="Path to the reflections notebook",
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path("monday_tasks.csv"),
        help="Task register file",
    )
    parser.add_argument(
        "--task-agent",
        action="store_true",
        help="Run the Codex task agent loop instead of a single analysis pass",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="Polling interval in seconds for the task agent",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=0,
        help="Optional safety cap for task-agent cycles (0 = infinite)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.task_agent:
        agent = CodexTaskAgent(
            tasks_path=args.tasks,
            memory_path=args.memory,
            notes_path=args.notes,
            log_path=args.log,
            poll_interval=args.interval,
        )
        max_cycles = args.max_cycles if args.max_cycles > 0 else None
        agent.run_loop(max_cycles=max_cycles)
        return

    memory = load_memory(args.memory)
    documents = load_documents(args.paths)

    ensure_tasks_file(args.tasks)

    engine = MondayEngine(memory)
    results = engine.run(documents)

    if results:
        output = format_result(results[-1])
        print(output)

    save_memory(args.memory, memory)
    append_log(args.log, results)
    append_notes(args.notes, results)


if __name__ == "__main__":
    main()

