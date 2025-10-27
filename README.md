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

## Google Apps Script automation hub

The `Code.gs` script can be deployed as an Apps Script web app to wire common
productivity tools on your phone back into ChatGPT. Configure the required
secrets via **Project Settings → Script Properties**:

| Property | Description |
| --- | --- |
| `OPENAI_API_KEY` | API key for the OpenAI Chat Completions endpoint. |
| `PROMPT_SHEET_ID` | (Optional) Spreadsheet ID for the `Prompts` sheet that queues user prompts. |
| `WATCH_FOLDER_ID` | Drive folder ID whose recent changes should be summarised. |
| `GITHUB_TOKEN` | GitHub personal access token for repository access. |
| `GITHUB_REPO` | Target repository in `owner/name` format. |
| `ZAPIER_WEBHOOK_URL` | Zapier catch hook URL that receives the aggregated payload. |

Key helper functions:

- `processSheetPrompts()` – reads queued prompts from the `Prompts` sheet and
  writes back ChatGPT answers.
- `summarizeDriveFolder()` – produces a German summary of recent Drive files.
- `fetchGitHubDigest()` – fetches open issues from GitHub and summarises them.
- `runAutomationHub()` – combines the daily assistant report, Drive summary,
  GitHub digest and optional sheet prompts into a single payload that gets
  pushed to Zapier for further automations.

Use time-based triggers to run `runAutomationHub` or `startDay` on a schedule
and let Zapier distribute the result to any mobile apps that should receive it.