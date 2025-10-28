# rag

This repository now includes an implementation of **MONDAY.exe** (codename
“E.R.G.” – Evidence Reasoning Generator).  The `monday.py` module can ingest a
collection of chat logs or archival documents and iteratively run the Leiden
cycle to produce auditable insights, truth chains, and self-reflective
meta-analyses.  Each run updates persistent artefacts:

- `monday_memory.json` – stores the latest improvement score and run metadata.
- `monday_log.csv` – append-only history of iterations and audit metrics.
- `monday_notes.md` – reflections emitted by the EmergentReflectionCore.
- `monday_tasks.csv` – bootstrap task ledger for future extensions.

Run MONDAY.exe from the repository root:

```bash
python monday.py path/to/archives
```

If no paths are supplied the engine will look for chat exports and list files in
the repository root (e.g. `_chat*.txt`, `*Liste*.md`, Codex manifests) and
process every discovered document automatically. This makes it easy to drop new
lists into the project without updating the command line arguments. When no
matching files are found the engine still initialises its state and records the
absence of evidence, ready for subsequent iterations with real data.

## Codex Task Agent quickstart

The repository also bundles a lightweight task-processing loop that watches the
`monday_tasks.csv` ledger and automatically updates task status while persisting
reflections and intermediate metrics to the standard MONDAY artefacts.

```bash
python monday.py --task-agent --interval 30 --max-cycles 0
```

- `--task-agent` switches the CLI into the Codex task agent mode.
- `--interval` controls how many seconds the agent waits between polling
  iterations (set `0` to process continuously during tests).
- `--max-cycles` can be used to stop the loop after a fixed number of iterations
  (default `0` keeps it running until you press `Ctrl+C`).

The agent reads pending entries from `monday_tasks.csv`, marks them as
completed, and writes supporting context to:

- `monday_memory.json` – stores per-task snapshots under the `tasks` key.
- `monday_log.csv` – captures each processed task as a timestamped log row.
- `monday_notes.md` – appends bullet-point reflections for traceability.

Stop the agent at any point with `Ctrl+C`; all artefacts remain on disk for the
next run.
