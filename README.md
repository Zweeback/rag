# rag

Dieses Repository enthält den Alice-Prompt, ein Skript für einen autonomen
Codex-Iterationsloop sowie eine kleine Weboberfläche für einen Ping-Pong-Chat
mit DeepSeek.

## Prompt-Arsenal für den Codex-Loop

Die Datei [`codex_prompts.md`](codex_prompts.md) bündelt fertig formulierte
System- und Iterationsprompts inklusive Modulaufträgen, die du direkt in den
`codex_auto_loop` einspeisen kannst. Kopiere die JSON-Blöcke in deine
Codex-Sitzung oder verwende sie als Vorlage für `next_codex_prompt.json`, um
gezielt neue Module wie `clock_core.py`, `chunker.py` oder `replicator.py`
anzustoßen.

## Verzeichnisübersicht

Eine vollständige, automatisch generierte Strukturübersicht des Repositorys
findest du in [`docs/structure.md`](docs/structure.md). Die Datei listet alle
Ordner und Dateien inklusive der importierten Ressourcen auf und eignet sich
als Nachschlagewerk, wenn du den Projektumfang schnell erfassen oder die
Ablage mit deinen lokalen Kopien abgleichen möchtest.

## Auto-Iteration starten

1. Installiere Abhängigkeiten (mindestens `pyyaml`, für OpenAI/Ollama zusätzlich `requests`).
   ```bash
   pip install pyyaml requests
   ```
2. Passe die Ziele in `codex.yaml` an dein Projekt an.
3. Lege das Zielprojekt im Ordner, der unter `workdir` konfiguriert ist (Standard: `./project`).
4. Wähle den gewünschten Adapter:
   - `mock` (Standard) – führt keine echten Änderungen durch, ideal zum Trockenlauf.
   - `openai` – nutzt die Chat-Completions-API (`OPENAI_API_KEY`, optional `OPENAI_BASE_URL`).
   - `ollama` – ruft einen lokalen Ollama-Server auf (`OLLAMA_BASE_URL`, Default `http://localhost:11434`).
   Setze entweder `CODEX_LOOP_ADAPTER=<adapter>` oder überschreibe `adapter` in
   `codex.yaml`.
5. Passe ggf. Modellname, Temperatur oder Befehle in `codex.yaml` an.
6. Starte den Loop:

   ```bash
   python codex_auto_loop.py codex.yaml
   ```

7. Analysiere die Iterationsprotokolle im Verzeichnis `.codex_logs`.

### Windows + LM Studio (Mistral) Schnellstart

Falls du die Automatisierung auf einem Windows-System mit LM Studio und einem
lokal gehosteten Mistral-Modell einsetzen möchtest, findest du eine vollständige
Schritt-für-Schritt-Anleitung in [`docs/windows_lmstudio.md`](docs/windows_lmstudio.md).
Die Kurzfassung:

1. Installiere Python 3.11+ sowie Git über die offiziellen Installer und
   aktiviere bei Python die Option „Add python.exe to PATH“.
2. Richte eine virtuelle Umgebung ein, installiere die Abhängigkeiten aus
   `requirements.txt` und passe `codex.yaml` an.
3. Starte in LM Studio den lokalen Server im OpenAI-kompatiblen Modus (Standard
   Port `1234`) und lade das gewünschte Mistral-Modell.
4. Setze in PowerShell `OPENAI_BASE_URL="http://localhost:1234/v1"` und
   `OPENAI_API_KEY="lm-studio"` (Dummy-Key) und wähle den Adapter `openai`.
5. Führe den Loop per `python codex_auto_loop.py codex.yaml` aus oder plane ihn
   über den Windows-Taskplaner.

Die Detailanleitung deckt außerdem Automatisierungsthemen wie geplante Läufe,
Log-Ablage, GitHub-Backups sowie optionale Audio-/Weboberflächen ab.

### Automatischer GitHub-Sync aus dem Loop

Der Auto-Loop kann nach jeder Iteration ausgewählte Artefakte über die
GitHub-Contents-API sichern. Aktiviere dazu in `codex.yaml` den Block
`github_sync` und lege fest, welche Dateien oder Ordner übertragen werden
sollen:

```yaml
github_sync:
  enabled: false               # auf true setzen, sobald Repository & Token bereitstehen
  repository: deinuser/deinrepo # Ziel-Repository (owner/name)
  branch: main                  # optionaler Ziel-Branch
  remote_base: codex_logs       # Unterordner im Ziel (leer = Repo-Wurzel)
  message_template: "Codex iteration {iter_label}"  # Platzhalter siehe unten
  paths:
    - ".codex_logs/{iter_label}.json"
```

* Token werden weiterhin über `GITHUB_TOKEN` aus der Umgebung gelesen.
* Verfügbare Platzhalter: `{iter_label}` (z. B. `iter_001`), `{iteration_number}`
  (z. B. `001`) und `{log_dir}`.
* Für die finale Gesamthistorie lädt der Loop automatisch
  `{log_dir}/history.json` hoch.

Falls `github_sync.py` nicht importiert werden kann (z. B. weil `requests`
fehlt), wird der Upload übersprungen und eine Hinweiszeile ausgegeben.

### Hinweise zu echten LLM-Adaptern

- Antworten müssen gültiges JSON liefern (siehe `system_prompt` in `codex.yaml`).
- Bei Evaluierungen erhält das Modell automatisch Kontext (`artifacts`, `logs`).
- Fehlerhafte oder fehlende Antworten brechen den Loop mit einer klaren
  Fehlermeldung ab (`Adapter-Fehler …`).

## Dateien

- `alice.md` – Strategierahmen für die Figur Alice.
- `codex_auto_loop.py` – Hauptskript des Propose→Apply→Test→Evaluate→Revise-Loops.
- `alice_autoloop.py` – Zusatzmodul für Audit-Scoring (Relevanz, Spezifität, Evidenz,
  Sicherheit, Actionability) inklusive SQLite-Ledger und Artefakt-Export.
- `codex.yaml` – Beispielkonfiguration inklusive Guardrails und Erfolgskriterien.

Viel Erfolg bei der Monetarisierung deiner Ideen!

## DeepSeek Ping-Pong Chat im Browser

1. Installiere die Web-Abhängigkeiten:
   ```bash
   pip install -r requirements.txt
   ```
2. Setze deinen DeepSeek-API-Key (und optional weitere Parameter):
   ```bash
   export DEEPSEEK_API_KEY="sk-..."
   export DEEPSEEK_MODEL="deepseek-chat"  # optional
   export DEEPSEEK_SYSTEM_PROMPT="Du antwortest fokussiert und freundlich."  # optional
   export DEEPSEEK_API_URL="https://api.deepseek.com/v1/chat/completions"      # optional Override
   export DEEPSEEK_API_TIMEOUT=45          # optional, Sekunden
   export DEEPSEEK_MAX_HISTORY_TURNS=12    # optional, Anzahl Ping-Pong-Paare
   export DEEPSEEK_MAX_OUTPUT_TOKENS=800   # optional, Begrenzung für Antworten
   export DEEPSEEK_TEMPERATURE=0.6         # optional, Kreativität
   ```
3. Starte den lokalen Server:
    ```bash
    uvicorn app.main:app --reload
    ```
4. Öffne `http://127.0.0.1:8000` im Browser und starte den Ping-Pong-Dialog.

Der Browser-Client bietet einen optionalen System-Prompt, einen Reset-Button,
Statusmeldungen samt Token-Zählung sowie eine automatische Health-Prüfung der
API. Der Verlauf wird clientseitig gehalten und bei jedem Request an das
Backend mitgeschickt, damit DeepSeek den Kontext kennt.

## Iterationen mit Audit-Scoring protokollieren

Das Modul `alice_autoloop.py` erweitert die klassische Schleife um eine
persistente SQLite-Datenbank und Auswertungen nach den Kriterien Relevance,
Specificity, Evidence, Safety und Actionability.

1. Optional zusätzliche Pakete installieren:
   ```bash
   pip install sentence-transformers openai chromadb
   ```
   Alle drei Bibliotheken sind optional – ohne sie greift das Skript auf einen
   Keyword-basierten Fallback zurück. Für OpenAI muss außerdem `OPENAI_API_KEY`
   gesetzt sein. `chromadb` aktiviert einen persistenten Vektor-Index, sobald
   auch eine Embedding-Quelle verfügbar ist.
2. (Optional) Evidenzschnipsel ins RAG einspeisen:
   ```python
   from alice_autoloop import ingest_chunk

   chunk_id = ingest_chunk("Skalierungsplan Q2", source="notebook")
   print("Chunk gespeichert:", chunk_id)
   ```
3. Prompt- und Antworttext als Dateien speichern und anschließend protokollieren:
   ```bash
   python alice_autoloop.py prompt.txt output.txt --metadata '{"adapter": "mock"}'
   ```
   Der Aufruf legt (standardmäßig) `alice_autoloop.db` an, speichert den Eintrag
   zusätzlich – falls konfiguriert – in einer Chroma-Vektordatenbank,
   extrahiert ToDos, speichert Code-Blöcke als Evidenz und erzeugt ausführbare
   Skripte im Ordner `scripts/`.
5. (Optional) Vektorindex konfigurieren:
   ```bash
   export ALICE_CHROMA_PATH=.chroma_store          # Persistente Ablage
   export ALICE_CHROMA_COLLECTION=alice_embeddings # optionaler Name
   ```
   Mit diesen Variablen nutzt `alice_autoloop.py` automatisch eine Chroma-
   Collection und beantwortet `rag_retrieve`-Anfragen über semantische
   Ähnlichkeit, sofern eine Embedding-Quelle aktiv ist.
4. Abrufen der Scores und Artefakte:
   ```python
   from alice_autoloop import log_iteration

   summary = log_iteration(prompt_text, response_text)
   print(summary.scores)
   ```

Die gespeicherten Daten eignen sich als Grundlage für Dashboards (z. B.
Streamlit) oder für automatische Schwellenwert-Anpassungen in weiteren
Iterationsschleifen.

## Artefakte sicher nach GitHub hochladen

Um Iterationslogs oder Skripte zentral zu archivieren, enthält das Repository
optional `github_sync.py`. Das Skript aktualisiert Dateien in einem bestehenden
GitHub-Repository über die Contents-API.

1. Erstelle (falls noch nicht vorhanden) ein Personal Access Token mit dem
   Scope `repo` und speichere es **nicht** im Klartext, sondern als
   Umgebungsvariable:
   ```bash
   export GITHUB_TOKEN="ghp_xxx"
   ```
2. Installiere die erforderliche Abhängigkeit:
   ```bash
   pip install requests
   ```
3. Lade Dateien hoch, zum Beispiel alle Skripte aus `.codex_logs` in einen
   Unterordner `artifacts` eines privaten Repositories:
   ```bash
   python github_sync.py deinuser/deinrepo .codex_logs --remote-base artifacts --message "Upload codex logs"
   ```

Das Skript ermittelt automatisch, ob Dateien bereits existieren und übermittelt
sie mit einem Commit pro Aufruf. Token werden ausschließlich aus der
Umgebung gelesen, sodass keine sensiblen Daten in Prompt-Historien landen.
