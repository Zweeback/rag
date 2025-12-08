"""Knowledge base implementation for CogniDistill."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .openai_custom_entity import build_openai_custom_entity_payload

from .entities import KnowledgeEntity, KnowledgeEntityCollection
from .parsing import extract_entities


@dataclass
class QualityAssessment:
    consistency: float
    completeness: float
    relevance: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "consistency": self.consistency,
            "completeness": self.completeness,
            "relevance": self.relevance,
        }


class KnowledgeBase:
    """In-memory knowledge base with self-improvement capabilities."""

    def __init__(self, *, min_confidence_threshold: float = 0.7) -> None:
        self.entities: KnowledgeEntityCollection = KnowledgeEntityCollection()
        self.min_confidence_threshold = min_confidence_threshold
        self.change_log: List[str] = []

    # ------------------------------------------------------------------
    # Ingestion & improvement
    # ------------------------------------------------------------------
    def ingest_text(
        self,
        text: str,
        *,
        sources: Optional[Sequence[str]] = None,
        auto_improve: bool = True,
    ) -> List[KnowledgeEntity]:
        """Ingest text and optionally integrate into the knowledge base."""

        extracted = extract_entities(text, sources=sources)
        if not auto_improve:
            return extracted

        for entity in extracted:
            self.integrate_entity(entity)
        return extracted

    def integrate_entity(self, entity: KnowledgeEntity) -> None:
        """Merge an entity into the knowledge base, resolving conflicts."""

        existing = self.entities.get(entity.entity_id)
        if existing is None:
            self.entities.add(entity)
            self.change_log.append(f"[NEUE_ENTITÄT] {entity.entity_id}")
            return

        if entity.confidence >= existing.confidence:
            existing.update(
                content=entity.content,
                confidence=entity.confidence,
                sources=entity.sources,
            )
            for relation, targets in entity.relationships.items():
                for target in targets:
                    existing.add_relationship(relation, target)
            self.change_log.append(f"[VERBESSERT] {entity.entity_id}")
        else:
            self.change_log.append(f"[KONFLIKT] {entity.entity_id}")

    # ------------------------------------------------------------------
    # Query & retrieval
    # ------------------------------------------------------------------
    def query(self, question: str, *, limit: int = 5) -> Tuple[str, float, List[KnowledgeEntity]]:
        """Return a condensed answer for a question using keyword search."""

        keywords = _tokenise(question)
        scored_entities: List[Tuple[float, KnowledgeEntity]] = []
        for entity in self.entities.values():
            score = self._similarity_score(entity, keywords)
            if score <= 0:
                continue
            scored_entities.append((score, entity))

        if not scored_entities:
            return ("Keine passenden Informationen gefunden.", 0.0, [])

        scored_entities.sort(key=lambda item: item[0], reverse=True)
        selected_entities = [entity for _, entity in scored_entities[:limit]]
        answer = " ".join(entity.content for entity in selected_entities)
        confidence = sum(entity.confidence for entity in selected_entities) / len(selected_entities)
        return answer, confidence, selected_entities

    def _similarity_score(self, entity: KnowledgeEntity, keywords: Iterable[str]) -> float:
        content_tokens = _tokenise(entity.content)
        overlap = content_tokens & set(keywords)
        if not overlap:
            return 0.0
        return entity.confidence * (len(overlap) / len(content_tokens | set(keywords)))

    # ------------------------------------------------------------------
    # Quality assessment & statistics
    # ------------------------------------------------------------------
    def assess_quality(self) -> QualityAssessment:
        """Return heuristic quality metrics for the knowledge base."""

        if not self.entities:
            return QualityAssessment(consistency=1.0, completeness=0.0, relevance=0.0)

        confidence_values = [entity.confidence for entity in self.entities.values()]
        avg_confidence = sum(confidence_values) / len(confidence_values)

        conflicts = sum(1 for entry in self.change_log if entry.startswith("[KONFLIKT]"))
        consistency = max(0.0, 1.0 - conflicts / max(1, len(self.change_log)))

        completeness = min(1.0, len(self.entities) / 20)

        relevance = min(1.0, avg_confidence)

        return QualityAssessment(consistency=consistency, completeness=completeness, relevance=relevance)

    # ------------------------------------------------------------------
    # Export & persistence
    # ------------------------------------------------------------------
    def export(self, format_: str) -> str:
        """Export the knowledge base to a supported format."""

        format_ = format_.lower()
        if format_ == "json":
            return self._export_json()
        if format_ == "markdown":
            return self._export_markdown()
        if format_ == "xml":
            return self._export_xml()
        if format_ == "csv":
            return self._export_csv()
        if format_ in {"openai_custom", "openai-custom", "openai"}:
            return self._export_openai_custom_entity()
        raise ValueError(f"Unsupported export format: {format_}")

    def _export_json(self) -> str:
        import json

        return json.dumps(self.snapshot(), ensure_ascii=False, indent=2)

    def _export_markdown(self) -> str:
        lines = ["# CogniDistill Wissensbasis", ""]
        for entity in self.entities.values():
            lines.append(f"## {entity.entity_id} ({entity.entity_type})")
            lines.append(entity.content)
            lines.append(f"- Confidence: {entity.confidence:.2f}")
            lines.append(f"- Quellen: {', '.join(entity.sources)}")
            if entity.relationships:
                lines.append("- Beziehungen:")
                for relation, targets in entity.relationships.items():
                    joined = ", ".join(targets)
                    lines.append(f"  - {relation}: {joined}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _export_xml(self) -> str:
        lines = ["<knowledgeBase>"]
        for entity in self.entities.values():
            lines.append(f"  <entity id=\"{entity.entity_id}\" type=\"{entity.entity_type}\">")
            lines.append(f"    <content>{_escape_xml(entity.content)}</content>")
            lines.append(f"    <confidence>{entity.confidence:.2f}</confidence>")
            lines.append("    <sources>")
            for source in entity.sources:
                lines.append(f"      <source>{_escape_xml(source)}</source>")
            lines.append("    </sources>")
            if entity.relationships:
                lines.append("    <relationships>")
                for relation, targets in entity.relationships.items():
                    for target in targets:
                        lines.append(
                            "      <relationship type=\"{relation}\" target=\"{target}\"/>".format(
                                relation=_escape_xml(relation), target=_escape_xml(target)
                            )
                        )
                lines.append("    </relationships>")
            lines.append("  </entity>")
        lines.append("</knowledgeBase>")
        return "\n".join(lines)

    def _export_csv(self) -> str:
        import csv
        from io import StringIO

        buffer = StringIO()
        fieldnames = [
            "entity_id",
            "entity_type",
            "content",
            "confidence",
            "sources",
            "version",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for entity in self.entities.values():
            writer.writerow(
                {
                    "entity_id": entity.entity_id,
                    "entity_type": entity.entity_type,
                    "content": entity.content,
                    "confidence": f"{entity.confidence:.2f}",
                    "sources": ";".join(entity.sources),
                    "version": entity.version,
                }
            )
        return buffer.getvalue()

    def _export_openai_custom_entity(self) -> str:
        import json

        payload = build_openai_custom_entity_payload(self.snapshot())
        return json.dumps(payload, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, object]:
        """Return a serialisable snapshot of the knowledge base."""

        return {
            "entities": self.entities.to_dict(),
            "relationships": self._collect_relationships(),
            "metadata": {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "entity_count": len(self.entities),
            },
        }

    def _collect_relationships(self) -> List[Dict[str, str]]:
        relationships: List[Dict[str, str]] = []
        for entity in self.entities.values():
            for relation, targets in entity.relationships.items():
                for target in targets:
                    relationships.append(
                        {"from_entity": entity.entity_id, "relation": relation, "to_entity": target}
                    )
        return relationships


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _tokenise(text: str) -> set[str]:
    import re

    return {token for token in re.findall(r"[\wäöüÄÖÜß-]+", text.lower()) if len(token) > 2}


def _escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
