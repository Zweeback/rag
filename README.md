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

If no paths are supplied the engine will initialise its state and record the
absence of evidence, ready for subsequent iterations with real data.