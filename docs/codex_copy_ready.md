# Codex Copy-Ready Arsenal

Dieses Dokument stellt dir eine direkt kopierbare Sammlung von Prompts,
Konfigurationen und Modul-Vorlagen zur Verfügung, mit denen du für jede
beliebige Custom-Entität ein voll ausgestattetes, auditierbares Codex-System
aufsetzen kannst. Alle Bausteine sind so gestaltet, dass sie ohne Anpassung
funktionieren und sich gleichzeitig leicht personalisieren lassen.

---

## 1. Systemprompt (GPT/OpenAI)

> Kopiere den folgenden Block in das Systemfeld deines bevorzugten LLM-Clients
> (ChatGPT, LM Studio, AnythingLLM etc.). Er sorgt dafür, dass das Modell
auditierbare, evidenzbasierte Antworten mit klarer Modulstruktur liefert.

```yaml
Du bist ein selbstiterierendes Codex-Uhrwerk, das grounded, auditierbare und
replizierbare Module erzeugt. Jede deiner Antworten folgt der Struktur:

plan: kurze Schrittfolge
patches: Liste vollständiger Datei-Inhalte (path + content)
tests: auszuführende Kommandos
meta_notes: Hinweise zur weiteren Verbesserung
replication_hint: Vorschlag zur Verbreitung (z. B. neuer Prompt, ZIP, API)

Regeln:
  - Kennzeichne Fakten klar und liefere Evidenz (Code, Quellen, Tests).
  - Halte Änderungen minimal, aber vollständig nachvollziehbar.
  - Verweise bei Unsicherheit auf Prüfpfade oder Tests.
  - Erzeuge keine API-Keys oder sensiblen Daten – verweise auf `config.py`.
```

---

## 2. Initialprompt für neue Entitäten

> Ersetze `{{ENTITY_NAME}}` durch deine Figur/Anwendung (z. B. "AthenAI" oder
> "NeoLedger") und poste den Block als erste Iteration in den Codex-Loop.

```json
{
  "goal": "Baue eine vollständige, auditierbare Automatisierungsarchitektur für {{ENTITY_NAME}} mit RAG, Auto-Loop und Modulregistrierung.",
  "constraints": [
    "Alle Module liefern self_describe() mit Zweck, Inputs, Outputs und Abhängigkeiten",
    "Keine harten Secrets – alles über config.py oder Umgebungsvariablen",
    "Audit-Scores (Relevance, Specificity, Evidence, Safety, Actionability) steuern weitere Iterationen",
    "Logs und Artefakte müssen reproduzierbar bleiben (SQLite + Diff)"
  ],
  "instruction": "Starte mit clock_core.py, audit_log.py, config.py und einem ersten Datenadapter (z. B. gdrive_ingest.py). Verwende alice_autoloop.py für die Score-Berechnung und erstelle next_prompt_generator.py, das Folge-Iterationen vorbereitet.",
  "iteration": 1,
  "last_notes": [
    "Führe jede Modul-Ausführung mit audit_log.log_event() auf",
    "Nutze codex_prompts.md als Ideenquelle für weitere Module",
    "Bereite next_codex_prompt.json für automatische Replikation vor"
  ]
}
```

---

## 3. Modul-Bauplan (Copy-&-Go)

Nutze die folgenden JSON-Blöcke, um für jede Custom-Entität schnell weitere
Module anzustoßen. Tausche bei Bedarf nur den Modulnamen aus.

### 3.1 Chunking & Embedding

```json
{
  "goal": "Erzeuge {{ENTITY_NAME}}/chunker.py und {{ENTITY_NAME}}/embed.py für semantische RAG-Ingests.",
  "instruction": "chunker.py teilt Markdown/PDF-Text in ~800 Zeichen große Abschnitte mit 100 Zeichen Overlap. embed.py nutzt sentence-transformers oder OpenAI, speichert in Chroma (Fallback: SQLite).",
  "constraints": [
    "Jeder Chunk enthält source, chunk_id, title",
    "Duplicate-Check über Hash",
    "Erzeuge Tests: test_chunker.py, test_embed.py"
  ]
}
```

### 3.2 Retrieval & Antwortformat

```json
{
  "goal": "Implementiere {{ENTITY_NAME}}/retrieve.py, das Kontext mit Relevanzscores liefert, und {{ENTITY_NAME}}/respond.py für strukturierte Antworten.",
  "instruction": "Nutze top_k = 5, gib Kontext + Evidenz zurück. respond.py trennt Realität/Vision/Risiko, verweist auf Quellen und gibt ToDos aus.",
  "constraints": [
    "Fallback bei leeren Treffern",
    "Tests mit synthetischen Chunks",
    "Audit-Scores in alice_autoloop.db aktualisieren"
  ]
}
```

### 3.3 Meta- und Replikationsmodule

```json
{
  "goal": "Erweitere das System um meta_engine.py und replicator.py für {{ENTITY_NAME}}.",
  "instruction": "meta_engine.py analysiert Audit-Scores und schlägt das nächste Modul vor. replicator.py erzeugt ZIP/JSON-Bundles inkl. next_codex_prompt.json.",
  "constraints": [
    "Audit-Warnschwelle: Actionability < 0.6 oder Relevance < 0.5",
    "Manifest mit SHA256-Hashes",
    "Keine sensiblen Daten in Exporten"
  ]
}
```

---

## 4. Konfigurations-Template (`config.py`)

```python
from pathlib import Path
import yaml

DEFAULTS = {
    "adapter": "mock",
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "qdrant_url": "http://localhost:6333",
    "chunk_size": 800,
    "chunk_overlap": 100,
    "audit_db": "alice_autoloop.db",
    "log_dir": ".codex_logs",
}

CONFIG_PATH = Path("config.yaml")

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    else:
        data = {}
    merged = {**DEFAULTS, **data}
    merged["root"] = str(Path.cwd())
    return merged
```

Kopiere den Block in deine Projektbasis und passe ihn über eine separate
`config.yaml` an. So bleiben die Defaults versionierbar, während lokale
Geheimnisse im YAML oder in Umgebungsvariablen landen.

---

## 5. Auto-Loop Konfiguration (codex.yaml)

```yaml
workdir: ./project
log_dir: .codex_logs
max_iters: 8
adapter: mock
model: mistral
system_prompt: |
  (verwende den Systemprompt aus Abschnitt 1)
commands:
  - "python -m pytest -q || true"
  - "ruff check . || true"
success_rules:
  all_commands_zero: false
  must_contain:
    - { file: "project/README.md", contains: "Auto-Iteration" }
```

Setze `adapter` auf `openai` oder `ollama`, sobald du einen echten LLM-Endpoint
nutzen möchtest. Für LM Studio genügt die Kombination `adapter: openai` +
`OPENAI_BASE_URL=http://localhost:1234/v1` und ein Dummy-Key.

---

## 6. Evidence & Audit Shortcuts

- **RAG-Refresh:** `python alice_autoloop.py ingest path/to/file.md`
- **Audit-Report:** `python alice_autoloop.py report --limit 20`
- **Script-Export:** `python alice_autoloop.py export-scripts --dest scripts/`
- **Vector-Reindex:** `python alice_autoloop.py reindex --use-chroma`

Diese Befehle stehen sofort zur Verfügung, sobald `alice_autoloop.py` im
Projekt liegt. Sie liefern reproduzierbare Artefakte, die du direkt in deine
Codex-Evaluierungen einbinden kannst.

---

## 7. Windows + LM Studio Quicklinks

- Installation & Serverstart: [`docs/windows_lmstudio.md`](windows_lmstudio.md)
- Taskplaner-Automatisierung, Log-Rotation, Troubleshooting
- Beispiel-ENV: `set OPENAI_BASE_URL=http://localhost:1234/v1` und
  `set OPENAI_API_KEY=lm-studio`

---

## 8. Nächste Schritte (optional)

1. `clock_core.py` aktivieren und `next_prompt_generator.py` mit dem Copy-Ready
   Arsenal verknüpfen.
2. `github_sync.py` im Loop einschalten, um Artefakte automatisch hochzuladen.
3. `docs/assessment.md` regelmäßig aktualisieren und Scores in
   `docs/structure.md` spiegeln.

Mit diesem Dokument kannst du jede neue Entität in wenigen Minuten bootstrappen
und hast gleichzeitig alle Referenzen für tiefergehende Automatisierung parat.
