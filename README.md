# Dortmund City Sandbox – Bruce Manor Airship Edition

"Dortmund City Sandbox" ist ein Unity-2022-LTS-Projekt (URP), das eine frei
begehbare Dortmund-Szene mit OpenStreetMap-Daten, einem steuerbaren Luftschiff
(„Bruce Manor“) sowie Jetpack-, Fahrzeug- und Passanten-Systemen vorbereitet.
Dieses Repository enthält zudem eine Python-Pipeline für OSM-/DEM-Daten,
CI/CD-Workflows auf Basis von GameCI und ein Google-Apps-Script zur
Orchestrierung neuer Builds.

## Projektüberblick

| Modul | Beschreibung |
| --- | --- |
| Player & Jetpack | Third-Person-Controller mit aktivierbarem Jetpack. |
| Bruce Manor | Luftschiff-Prefab mit Autopilot und Docking-Punkt am Phönixsee. |
| Vehicles & Traffic | Platzhalterfahrzeuge mit Schleifenverkehr. |
| Pedestrians | NavMesh-Agenten mit Zufallsbewegungen. |
| Day/Night & Weather | Zyklische Beleuchtung und dynamische Wetter-Presets. |
| Streaming | Additives Nachladen von Stadt-Tiles. |
| Savegame | Speichert Luftschiff-Position und Weltzustand. |

## Repository-Struktur

```
DortmundCitySandbox/    # Unity-Projekt (URP)
  Assets/Game/          # Gameplay-Skripte, Prefabs, Audio, UI
  Packages/             # manifest.json mit URP-Abhängigkeiten
  ProjectSettings/      # Unity-Projekteinstellungen
.github/workflows/      # GameCI Build/Test/Release
tools/                  # Python-Skripte für OSM/DEM und Pipeline
CodexConfig.yaml        # Metadaten für Automatisierungen
SETUP.md                # Einrichtung und lokale Builds
DATA_SOURCES.md         # Quellen, Attribution und Lizenzhinweise
Code.gs                 # Google Apps Script Orchestrator
appsscript.json         # Manifest für Apps Script
```

## Erste Schritte

1. **Unity installieren** – Version `2022.3.18f1` mit Universal Render Pipeline.
2. **Repository klonen** und Unity-Projekt `DortmundCitySandbox` öffnen.
3. **Pakete auflösen** – Unity importiert URP, Input System, Cinemachine usw.
4. **Tools vorbereiten** – `python -m venv .venv && source .venv/bin/activate`.
5. **OSM/DEM importieren** – siehe `SETUP.md` und `tools/`-Ordner.
6. **Builds** – GameCI-Workflows `build.yml`, `test.yml`, `release.yml` steuern
   Windows- und WebGL-Builds.

## Lizenz

- MIT-Lizenz für Code und Projektstruktur.
- Geodaten aus OpenStreetMap (ODbL) und Copernicus EU-DEM. Details siehe
  `DATA_SOURCES.md`.
