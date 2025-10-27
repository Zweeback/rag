import csv
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from monday import CodexTaskAgent, load_tasks


def write_tasks(tmp_path: Path, rows) -> Path:
    tasks_path = tmp_path / "monday_tasks.csv"
    with tasks_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["task_id", "description", "status", "notes"])
        writer.writerows(rows)
    return tasks_path


def test_load_tasks_reads_rows(tmp_path):
    tasks_path = write_tasks(
        tmp_path,
        [
            ["1", "Review documents", "todo", ""],
            ["2", "Already done", "completed", "checked"],
        ],
    )

    tasks = load_tasks(tasks_path)

    assert len(tasks) == 2
    assert tasks[0].task_id == "1"
    assert tasks[1].is_complete()


def test_agent_processes_pending_tasks_and_persists(tmp_path):
    tasks_path = write_tasks(
        tmp_path,
        [
            ["1", "Investigate anomalies", "todo", ""],
            ["2", "Completed work", "completed", "notes"],
        ],
    )
    memory_path = tmp_path / "memory.json"
    notes_path = tmp_path / "notes.md"
    log_path = tmp_path / "log.csv"

    agent = CodexTaskAgent(
        tasks_path=tasks_path,
        memory_path=memory_path,
        notes_path=notes_path,
        log_path=log_path,
        poll_interval=0,
    )

    processed = agent.process_pending_tasks()

    assert processed == 1

    updated_tasks = load_tasks(tasks_path)
    assert updated_tasks[0].is_complete()
    assert "Improvement Score" in updated_tasks[0].notes
    assert updated_tasks[1].notes == "notes"

    memory_content = json.loads(memory_path.read_text(encoding="utf-8"))
    assert memory_content["tasks"]["1"]["status"] == "completed"

    notes_text = notes_path.read_text(encoding="utf-8")
    assert "Task 1" in notes_text

    with log_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == ["timestamp", "version", "improvement_score", "truth_chains", "audit_drift"]
    assert rows[1][1].startswith("task:1:")
