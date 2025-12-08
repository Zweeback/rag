"""High level system orchestration for CogniDistill."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence

from .config import BOOTSTRAP_ENTITIES, SYSTEM_CONFIG
from .entities import KnowledgeEntity
from .knowledge_base import KnowledgeBase

COMMANDS = {"/lade", "/frage", "/export", "/statistik", "/verbessere", "/suche"}


@dataclass
class QueryResult:
    answer: str
    confidence: float
    supporting_entities: List[KnowledgeEntity]

    def to_dict(self) -> Dict[str, object]:
        return {
            "answer": self.answer,
            "confidence": self.confidence,
            "supporting_entities": [entity.to_dict() for entity in self.supporting_entities],
        }


class CogniDistillSystem:
    """Facade around the knowledge base providing command style operations."""

    def __init__(self, *, config: Optional[Dict[str, object]] = None) -> None:
        config = config or SYSTEM_CONFIG
        self.config = config
        self.kb = KnowledgeBase(
            min_confidence_threshold=config.get("min_confidence_threshold", 0.7)
        )
        for entity in BOOTSTRAP_ENTITIES.values():
            self.kb.integrate_entity(entity)

    # ------------------------------------------------------------------
    # User facing commands
    # ------------------------------------------------------------------
    def lade(self, text: str, *, sources: Optional[Sequence[str]] = None) -> List[KnowledgeEntity]:
        return self.kb.ingest_text(
            text,
            sources=sources,
            auto_improve=self.config.get("auto_improvement", True),
        )

    def frage(self, frage: str) -> QueryResult:
        answer, confidence, entities = self.kb.query(frage)
        return QueryResult(answer=answer, confidence=confidence, supporting_entities=entities)

    def export(self, format_: str) -> str:
        return self.kb.export(format_)

    def statistik(self) -> Dict[str, object]:
        quality = self.kb.assess_quality()
        return {
            "entities": len(self.kb.entities),
            "quality": quality.to_dict(),
            "change_log": list(self.kb.change_log),
        }

    def verbessere(
        self, entity_id: str, new_content: str, *, confidence: Optional[float] = None
    ) -> bool:
        entity = self.kb.entities.get(entity_id)
        if entity is None:
            return False
        confidence_value = confidence if confidence is not None else entity.confidence
        entity.update(content=new_content, confidence=confidence_value)
        self.kb.change_log.append(f"[VERBESSERT] {entity_id}")
        return True

    def suche(self, thema: str) -> List[KnowledgeEntity]:
        return self.kb.entities.find_by_keyword(thema)

    # ------------------------------------------------------------------
    # Command parsing
    # ------------------------------------------------------------------
    def handle_command(self, command: str) -> str:
        command = command.strip()
        if not command:
            return "Kein Befehl erkannt."

        if command.startswith("/lade "):
            text = command[len("/lade ") :]
            entities = self.lade(text)
            return f"{len(entities)} Entitäten geladen."
        if command.startswith("/frage "):
            frage = command[len("/frage ") :]
            result = self.frage(frage)
            return f"Antwort: {result.answer}\nConfidence: {result.confidence:.2f}"
        if command.startswith("/export "):
            format_ = command[len("/export ") :]
            return self.export(format_)
        if command.startswith("/verbessere "):
            _, _, rest = command.partition(" ")
            parts = rest.split(" ", 1)
            if len(parts) != 2:
                return "Ungültiger Verbessern-Befehl."
            entity_id, new_content = parts
            success = self.verbessere(entity_id, new_content)
            return "Entität aktualisiert." if success else "Entität nicht gefunden."
        if command.startswith("/suche "):
            thema = command[len("/suche ") :]
            results = self.suche(thema)
            if not results:
                return "Keine Entitäten gefunden."
            lines = [f"{entity.entity_id}: {entity.content}" for entity in results]
            return "\n".join(lines)
        if command == "/statistik":
            stats = self.statistik()
            lines = [f"Gesamtentitäten: {stats['entities']}"]
            quality = stats["quality"]
            lines.append(
                "Qualität – Konsistenz: {consistency:.2f}, Vollständigkeit: {completeness:.2f}, "
                "Relevanz: {relevance:.2f}".format(**quality)
            )
            if stats["change_log"]:
                lines.append("Änderungen:")
                lines.extend(stats["change_log"][-5:])
            return "\n".join(lines)

        return "Unbekannter Befehl."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def start_message() -> str:
        return (
            "CogniDistill System aktiviert. Bereit zur Wissensdistillation.\n\n"
            "Kernfähigkeiten:\n"
            "✓ Automatische Wissensextraktion\n"
            "✓ Selbstverbessernde Entitäten\n"
            "✓ Multiformat Export\n"
            "✓ Semantische Suche\n\n"
            "Bereit für Input. Geben Sie Text zum Verarbeiten oder eine Frage zum Abrufen ein.\n\n"
            "Verfügbare Befehle: /lade, /frage, /export, /statistik, /verbessere, /suche\n\n"
            "System: awaiting_input"
        )


def bootstrap_system() -> CogniDistillSystem:
    return CogniDistillSystem()
