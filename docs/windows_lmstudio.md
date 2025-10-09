# Windows-Automatisierung mit LM Studio & Mistral

Diese Anleitung beschreibt, wie du das Alice/Codex-Automationspaket auf einem
Windows-System betreibst, auf dem Python bereits installiert ist und LM Studio
mit einem lokal gehosteten Mistral-Modell läuft. Die Schritte decken sowohl die
Erstinbetriebnahme als auch wiederkehrende Automatisierungsaufgaben ab.

## 1. Voraussetzungen prüfen

1. **Windows 10/11** mit Administratorrechten.
2. **Python 3.11 oder neuer** installiert und beim Setup die Option „Add
   python.exe to PATH“ aktiviert.
3. **Git für Windows** installiert (inklusive Git Bash, optional für Komfort).
4. **LM Studio** installiert, ein Mistral-Modell heruntergeladen und getestet.
   - Öffne LM Studio, lade z. B. *Mistral-7B Instruct*, starte eine lokale
     Chat-Sitzung und stelle sicher, dass Antworten generiert werden.
5. Optional: **Visual Studio Code** oder eine andere IDE für bequemes Arbeiten.

## 2. Projekt auschecken und Umgebung vorbereiten

```powershell
cd C:\pfad\zu\deinem\workspace
git clone https://github.com/<dein-user>/rag.git
cd rag
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
pip install pyyaml requests
```

> 💡 Für optionale Funktionen installiere zusätzlich `sentence-transformers`,
> `chromadb` und `openai`.

## 3. LM Studio als OpenAI-kompatiblen Server starten

1. Öffne LM Studio und wechsle zur Registerkarte **Server**.
2. Wähle **OpenAI Compatible Server** und starte ihn (Standard-Port `1234`).
3. Aktiviere das gewünschte Mistral-Modell als Standardmodell.
4. Prüfe per Browser oder `curl`, ob `http://localhost:1234/v1/models`
   erreichbar ist.

## 4. Umgebungskonfiguration für den Codex-Loop

Setze in PowerShell (innerhalb der aktivierten virtuellen Umgebung):

```powershell
$env:CODEX_LOOP_ADAPTER = "openai"
$env:OPENAI_BASE_URL = "http://localhost:1234/v1"
$env:OPENAI_API_KEY = "lm-studio"    # LM Studio verlangt einen Token, der Wert ist beliebig
$env:CODEX_LOOP_MODEL = "mistral"     # entspricht dem in LM Studio ausgewählten Modell
```

Passe anschließend `codex.yaml` an, z. B.:

```yaml
model: ${CODEX_LOOP_MODEL:-mistral}
adapter: ${CODEX_LOOP_ADAPTER:-openai}
temperature: 0.2
```

## 5. Auto-Loop ausführen

```powershell
python codex_auto_loop.py codex.yaml
```

Der Loop erzeugt Logs in `.codex_logs\`, schreibt Patches ins konfigurierte
Arbeitsverzeichnis und legt – falls `github_sync` aktiviert ist – Uploads auf
GitHub an.

## 6. Wiederkehrende Automatisierung

### Taskplaner-Job anlegen

1. Öffne den Windows-Taskplaner und erstelle eine neue Aufgabe.
2. Trigger: Zeitplan wählen (z. B. stündlich).
3. Aktion: `powershell.exe` mit Argumenten
   `-ExecutionPolicy Bypass -File "C:\pfad\zu\rag\scripts\run_loop.ps1"`.
4. Erstelle `scripts\run_loop.ps1` mit folgendem Inhalt:

   ```powershell
   param(
       [string]$ConfigPath = "C:\pfad\zu\rag\codex.yaml"
   )

   $env:CODEX_LOOP_ADAPTER = "openai"
   $env:OPENAI_BASE_URL = "http://localhost:1234/v1"
   $env:OPENAI_API_KEY = "lm-studio"

   & "C:\pfad\zu\rag\.venv\Scripts\python.exe" "C:\pfad\zu\rag\codex_auto_loop.py" $ConfigPath
   ```

### Logs und Artefakte

- Nutze `github_sync` im `codex.yaml`, um JSON-Protokolle automatisch in ein
  privates GitHub-Repository zu spiegeln.
- Alternativ kannst du `OneDrive` oder `SharePoint` verwenden, indem du den
  Log-Ordner synchronisieren lässt.

## 7. Ping-Pong-Weboberfläche starten

Für die DeepSeek-Demo oder als Platzhalter für zukünftige Voice-WebApps:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
start http://127.0.0.1:8000
```

## 8. Troubleshooting

| Problem | Lösung |
| --- | --- |
| `ModuleNotFoundError: No module named 'yaml'` | `pip install pyyaml` in der aktiven Umgebung ausführen |
| LM Studio Server antwortet nicht | Sicherstellen, dass die Option „OpenAI Compatible Server“ aktiv ist und kein anderer Dienst Port 1234 blockiert |
| Patches werden nicht geschrieben | Prüfe Schreibrechte im `workdir` und ob das Modell gültige JSON-Antworten liefert |
| GitHub-Uploads schlagen fehl | `GITHUB_TOKEN` setzen und Repository/Branch in `codex.yaml` prüfen |

## 9. Nächste Schritte

- Optional ein Streamlit-Dashboard über `alice_autoloop.db` und `.codex_logs`
  bauen.
- Voice-Interface nachrüsten (z. B. mit Whisper + Edge TTS) und als weiteres
  Modul registrieren.
- `next_codex_prompt.json` automatisch durch `clock_core.py` erzeugen lassen,
  damit neue Iterationen ohne manuelles Eingreifen starten.

Viel Erfolg beim Betrieb von Alice auf Windows mit LM Studio!
