# Setup

## Voraussetzungen

- Unity Hub + Unity **2022.3.18f1** (URP)
- Python 3.10+
- Git LFS (empfohlen für spätere Assets)
- Optional: Node.js für zusätzliche Toolchains

## Unity-Projekt öffnen

1. Repository klonen: `git clone https://github.com/Zweeback/dortmund-city-sandbox.git`
2. Unity Hub öffnen und über *Add project from disk* den Ordner `DortmundCitySandbox` wählen.
3. Beim ersten Start URP und Input System importieren lassen. Fehlende Pakete werden
   automatisch aus `Packages/manifest.json` aufgelöst.

## OSM- und DEM-Daten generieren

1. Python-Umgebung aktivieren:
   ```bash
   cd tools
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Bounding Box konfigurieren (Standard: Dortmund Phönixsee). Werte können in
   `tools/pipeline.py` angepasst oder über Umgebungsvariablen gesetzt werden.
3. Pipeline ausführen:
   ```bash
   python pipeline.py --bbox 7.46 51.49 7.53 51.52 --dem-source copernicus
   ```
4. Exportierte Tiles befinden sich im Ordner `tools/output/`. Die erzeugten FBX/PNG/Heightmap-Dateien
   können in Unity importiert werden.

## Builds lokal erstellen

- **Windows (IL2CPP)**: `Unity -batchmode -projectPath ./DortmundCitySandbox -buildTarget Win64 -quit`
- **WebGL**: `Unity -batchmode -projectPath ./DortmundCitySandbox -buildTarget WebGL -quit`

Die GameCI-Workflows übernehmen diese Schritte automatisiert in CI.

## CI/CD einrichten

1. In GitHub Secrets folgende Werte hinterlegen:
   - `UNITY_LICENSE`
   - `UNITY_VERSION` (z.B. `2022.3.18f1`)
   - `OSM_BBOX`
   - `DEM_SOURCE`
2. WebGL-Deployment über GitHub Pages aktivieren (Branch `gh-pages`).
3. Release-Workflow (`release.yml`) erzeugt ZIP-Artefakte und optional Discord-Notifications.

## Troubleshooting

- Paketkonflikte: In Unity unter *Window > Package Manager* prüfen und ggf. `Reset Packages to defaults`.
- Pfadprobleme unter Windows: Powershell mit Administratorrechten starten und `Set-ExecutionPolicy RemoteSigned` setzen,
  wenn das Aktivieren des Python-Venv fehlschlägt.
