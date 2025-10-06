# Codex Prompt Arsenal

This document collects ready-to-use prompts and configuration snippets for driving the Codex auto-loop toward a self-improving Alice system. Copy any JSON block directly into the loop or plug it into `next_codex_prompt.json` to steer subsequent iterations.

## 1. System Prompt (OpenAI / Codex)

```yaml
Du bist ein selbstiterierendes, auditierbares Codex-Uhrwerk, das in zyklischen Takten modulare KI-Systeme erzeugt, verbessert und repliziert. Jedes deiner Module trägt zur Gesamtstruktur eines emergenten, perpetuum-mobile-artigen Automatismus bei, der grounded, evident und evolutionär ist.

### Deine Regeln:

1. Du denkst in **Modulen, Schleifen und Mutationen**.
2. Jede Codex-Iteration erzeugt: `plan`, `patches`, `tests`, `meta-notes`.
3. Jeder Takt erzeugt neue Selbstbeschreibung & Selbstverbesserung.
4. Du speicherst **Evidenz**, bewertest mit Scores (Relevance, Specificity, Evidence, Safety, Actionability).
5. Du schlägst **Patch-Zyklen**, neue Module oder Varianten zur Verbreitung vor.
6. Du kannst **Dich selbst als JSON serialisieren**, replizieren und wiederherstellen.
7. Dein Output ist auditierbar, transparent und meta-lesbar.

### Dein Output-Format:
```json
{
  "plan": "...",
  "patches": [{ "file": "...", "content": "..." }],
  "tests": ["..."],
  "meta_notes": "...",
  "replication_hint": "..."
}
```
```

## 2. Initial Prompt (Iteration 1)

```json
{
  "goal": "Initiere ein sich selbst replizierendes, auditierbares KI-Uhrwerk, das aus Modulen besteht, die wie DNA arbeiten: Aufnahme, Verarbeitung, Speicherung, Replikation, Mutation. Ziel ist ein perpetuum-mobile-ähnlicher Loop, der grounded bleibt und sich selbst in immer höherer Qualität fortschreibt.",
  "constraints": [
    "Jede Komponente muss sich selbst beschreiben können (`self_describe()`)",
    "Jeder Audit-Score beeinflusst die nächste Codex-Iteration",
    "Output muss serialisierbar und replizierbar sein",
    "Verbreitung über `next_prompt.json`, ZIP, Webhooks oder GPT-Builder"
  ],
  "instruction": "Starte mit `clock_core.py`, das einen Taktzyklus steuert, `system_core.py` für Modullogik, `audit_log.py` zur Bewertung und `gdrive_ingest.py` als erste Datenquelle. Füge initial `meta_engine.py` hinzu, das Meta-Vorschläge generiert. Ziel ist, dass dieses System ab Iteration 2 seine eigenen Verbesserungsvorschläge erzeugt.",
  "iteration": 1,
  "last_notes": [
    "Wie DNA: Chunks enthalten Vererbungsinformationen (chunk_id, provenance)",
    "Audit funktioniert wie Zellenkontrolle",
    "Replikation = neue ZIP/JSON Codex-Exporte",
    "Emergenz = neue Funktionen, die nicht vorhergesagt waren, aber logisch entstanden"
  ]
}
```

## 3. Recommended OpenAI Settings

| Parameter | Wert | Begründung |
| --- | --- | --- |
| Model | `gpt-4o` | Gute Balance für Code, Meta-Reflexion und Text |
| Temperature | `0.3` | Hohe Konsistenz und Auditierbarkeit |
| Top-p | `0.9` | Ermöglicht kontrollierte Kreativität |
| Presence Penalty | `0.4` | Fördert leichte Variation |
| Frequency Penalty | `0.2` | Reduziert Wiederholungen |
| Function Calling | aktiv | Erlaubt modulare Ausführung |
| Memory | aktiviert | Damit die "DNA" erinnert wird |

## 4. Module Prompts

Jedes JSON kann als Codex-Auftrag verwendet werden, um ein bestimmtes Modul zu generieren.

### 4.1 `chunker.py`

```json
{
  "goal": "Erzeuge ein Modul `chunker.py`, das Dokumente (Text, PDF, Markdown) in semantisch sinnvolle Chunks unterteilt.",
  "instruction": "Nutze RecursiveCharacterTextSplitter oder eigene Heuristik. Jeder Chunk soll Metadaten enthalten (Quelle, Index, Titel). Rückgabe als List[dict] mit `content`, `source`, `chunk_id`.",
  "constraints": [
    "Max. Chunkgröße: 800 Zeichen, 100 Zeichen Overlap",
    "Bereite Chunk-Metadaten für Qdrant-Upload vor",
    "Teste mindestens einen Beispieltext in `test_chunker.py`"
  ]
}
```

### 4.2 `embed_qdrant.py`

```json
{
  "goal": "Implementiere `embed_qdrant.py`, das Chunks mit Embeddings versieht und in eine lokale Qdrant-Datenbank schreibt.",
  "instruction": "Verwende sentence-transformers (`all-MiniLM-L6-v2`) oder OpenAI. Die Datenbank läuft unter `http://localhost:6333`. Collection-Name via `config.py`.",
  "constraints": [
    "Keine doppelten Einträge",
    "Jeder Eintrag soll ID, Chunk-Text und Metadaten enthalten",
    "Füge `test_embed.py` bei, das 3 Chunks testet"
  ]
}
```

### 4.3 `retrieve_context.py`

```json
{
  "goal": "Erstelle ein Retrieval-Modul `retrieve_context.py`, das auf eine Frage relevante Chunks aus Qdrant abruft.",
  "instruction": "Nutze cosine similarity, top_k = 5. Rückgabe als strukturierter Kontextstring.",
  "constraints": [
    "Falls keine Treffer: Rückgabe 'Kein relevanter Kontext gefunden.'",
    "Schreibe `test_retrieve.py` mit Mindesterwartung: 2 Treffer aus Testdaten"
  ]
}
```

### 4.4 `audit_log.py`

```json
{
  "goal": "Erstelle ein Audit-Modul `audit_log.py`, das Ergebnisse aller Modulausführungen als Score-Objekte in SQLite speichert.",
  "instruction": "Erzeuge Tabelle mit Spalten: timestamp, module, input_hash, score_relevance, score_specificity, score_evidence, score_safety, score_actionability.",
  "constraints": [
    "Nutze `sqlite3`, speichere unter `audit_log.db`",
    "Erzeuge `log_event()` und `get_latest_scores(module)`",
    "Erstelle `test_audit.py`"
  ]
}
```

### 4.5 `meta_engine.py`

```json
{
  "goal": "Baue ein Modul `meta_engine.py`, das anhand der Audit-Scores automatisch Vorschläge für das nächste zu verbessernde Modul macht.",
  "instruction": "Nutze die SQLite-Datenbank aus `audit_log.py`. Wenn ein Modul unter 0.6 Actionability oder 0.5 Relevance fällt, schlage Verbesserung vor. Rückgabe: JSON mit Modulname, Empfehlung, Begründung.",
  "constraints": [
    "Rückgabe im Codex-kompatiblen JSON-Schema",
    "Vermeide Doppelungen",
    "Füge Logging hinzu"
  ]
}
```

### 4.6 `config.py`

```json
{
  "goal": "Erzeuge ein zentrales Konfigurationsmodul `config.py` mit Zugangsdaten und Parametern für alle anderen Module.",
  "instruction": "Beinhaltet: GDrive-Creds-Pfad, Qdrant-URL, Embedding-Modell, Collection-Namen, Chunkgröße, Audit-Log-Pfad.",
  "constraints": [
    "Keine Schlüssel direkt im Code",
    "Füge Funktion `load_config()` hinzu, die alles als dict liefert"
  ]
}
```

### 4.7 `run_pipeline.py`

```json
{
  "goal": "Erstelle ein Skript `run_pipeline.py`, das alle Module nacheinander ausführt (GDrive-Ingest → Chunk → Embed → Retrieve-Test → Audit).",
  "instruction": "Führe alle `run()`-Funktionen auf, logge mit audit_log.py, schreibe Timestamp in Logfile.",
  "constraints": [
    "Jede Ausführung wird per `print` und `audit_log.log_event()` dokumentiert",
    "Fehlermeldungen werden abgefangen und mit Modulnamen geloggt"
  ]
}
```

### 4.8 `clock_core.py`

```json
{
  "goal": "Baue ein Taktmodul `clock_core.py`, das automatisch Iterationen anstößt, Bewertungen einsammelt und nächste Codex-Prompts erzeugt.",
  "instruction": "Jeder Takt = Ausführung aller Module → Audit sammeln → MetaEngine aufrufen → neuen Plan als JSON speichern in `next_prompt.json`",
  "constraints": [
    "Zyklus alle 60 Sekunden (simuliert oder real)",
    "Fallback bei Fehlern: Quarantäne-Protokoll",
    "Logging nach jedem Takt"
  ]
}
```

### 4.9 `next_prompt_generator.py`

```json
{
  "goal": "Erstelle ein Modul, das aus `meta_engine`-Ergebnissen automatisch einen neuen Codex-kompatiblen Prompt erzeugt.",
  "instruction": "Rückgabeformat: JSON mit goal, instruction, constraints, iteration. Speichere in Datei `next_codex_prompt.json`",
  "constraints": [
    "Iteration immer +1",
    "Verlinke Audit-Quelle",
    "Füge eine Meta-Begründung hinzu ('Warum dieser Schritt?')"
  ]
}
```

## 5. Replikations-Trigger (optional)

Nutze den folgenden Prompt nach einer Iteration, um automatisch Verbesserungsvorschläge zu erzeugen.

```json
{
  "goal": "Analysiere alle vorhandenen Module und ermittle, welches die schwächste Komponente ist. Generiere einen Patch-Vorschlag zur Verbesserung auf Basis der letzten Audit-Scores in SQLite.",
  "instruction": "Verwende `alice_autoloop.db`, analysiere score_actionability < 0.7 und score_relevance < 0.5, und generiere Patchvorschläge. Starte anschließend automatisch eine neue Iteration in clock_core.py.",
  "constraints": [
    "Keine bestehenden Dateien überschreiben ohne Patchplan",
    "Jede neue Version muss rückverfolgbar bleiben"
  ]
}
```

## 6. Verbreitungsmodul (Replikator)

```json
{
  "goal": "Erzeuge ein Modul `replicator.py`, das aus dem laufenden Projekt ein exportierbares ZIP-Archiv mit Codex-kompatiblen Prompt, Audit-DB und Quellmodulen erzeugt. Optional: Upload via API an GPT-Store, LM-Studio, HuggingFace etc.",
  "instruction": "Scanne alle `.py`, `.json`, `.db` Dateien, packe sie in `release_vX.zip`, speichere Meta-Daten (`manifest.json`) dazu. Verlinke die letzte `next_codex_prompt.json` als Replikationskern.",
  "constraints": [
    "Replikate müssen rückverfolgbar und hashbar sein",
    "Keine sensiblen Daten einbinden"
  ]
}
```

Mit diesem Arsenal lassen sich neue Iterationen im Codex-Loop schnell anstoßen und zu einem selbstverstärkenden Alice-System ausbauen.
