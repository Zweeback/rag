"""Default configuration and bootstrap entities for CogniDistill."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Mapping

from .entities import KnowledgeEntity

SYSTEM_CONFIG = {
    "min_confidence_threshold": 0.7,
    "auto_improvement": True,
    "relationship_detection": True,
    "version_control": True,
    "export_formats": ["json", "markdown", "xml"],
    "default_language": "de",
    "quality_metrics": ["consistency", "completeness", "relevance"],
}

_now = datetime.now(timezone.utc)

BOOTSTRAP_ENTITIES: Dict[str, KnowledgeEntity] = {
    "konzept_rag": KnowledgeEntity(
        entity_id="konzept_rag",
        entity_type="konzept",
        content=(
            "Retrieval-Augmented Generation verbindet Informationsabruf "
            "mit Textgenerierung"
        ),
        confidence=0.9,
        sources=["research_papers"],
        created=_now,
        updated=_now,
        version=1,
    ),
    "methode_wissensdistillation": KnowledgeEntity(
        entity_id="methode_wissensdistillation",
        entity_type="methode",
        content=(
            "Wissensdistillation extrahiert Kerninformationen aus großen "
            "Datenmengen"
        ),
        confidence=0.85,
        sources=["machine_learning_literature"],
        created=_now,
        updated=_now,
        version=1,
    ),
}


def serialize_bootstrap() -> Mapping[str, Mapping[str, object]]:
    """Return a serialisable view of the bootstrap entities."""

    return {entity_id: entity.to_dict() for entity_id, entity in BOOTSTRAP_ENTITIES.items()}
