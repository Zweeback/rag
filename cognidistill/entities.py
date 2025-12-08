"""Entity definitions used by CogniDistill."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional

VALID_ENTITY_TYPES = {"konzept", "fakt", "prozess", "relation", "methode"}


@dataclass
class KnowledgeEntity:
    """Representation of a structured knowledge entity."""

    entity_id: str
    entity_type: str
    content: str
    confidence: float
    sources: List[str]
    created: datetime
    updated: datetime
    version: int = 1
    relationships: MutableMapping[str, List[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(f"Unsupported entity type: {self.entity_type}")
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must lie between 0 and 1")
        if self.version < 1:
            raise ValueError("Version must be >= 1")

    def to_dict(self) -> Dict[str, object]:
        """Return a serialisable representation of the entity."""

        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "content": self.content,
            "confidence": self.confidence,
            "sources": list(self.sources),
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "version": self.version,
            "relationships": {
                relation: list(targets) for relation, targets in self.relationships.items()
            },
        }

    def update(
        self,
        *,
        content: Optional[str] = None,
        confidence: Optional[float] = None,
        sources: Optional[Iterable[str]] = None,
    ) -> None:
        """Update the entity with new information."""

        if content:
            self.content = content
        if confidence is not None:
            if not 0 <= confidence <= 1:
                raise ValueError("Confidence must lie between 0 and 1")
            self.confidence = confidence
        if sources:
            existing = set(self.sources)
            for source in sources:
                if source not in existing:
                    self.sources.append(source)
                    existing.add(source)
        self.version += 1
        self.updated = datetime.now(timezone.utc)

    def add_relationship(self, relation: str, target_id: str) -> None:
        """Link this entity to another entity."""

        targets = self.relationships.setdefault(relation, [])
        if target_id not in targets:
            targets.append(target_id)

    @staticmethod
    def generate_id(content: str, entity_type: str) -> str:
        """Generate a deterministic identifier based on content and type."""

        digest = hashlib.sha1(f"{entity_type}:{content}".encode("utf-8")).hexdigest()
        return f"{entity_type}_{digest[:12]}"


class KnowledgeEntityCollection(dict):
    """Helper container for knowledge entities."""

    def add(self, entity: KnowledgeEntity) -> None:
        self[entity.entity_id] = entity

    def find_by_keyword(self, keyword: str) -> List[KnowledgeEntity]:
        keyword_lower = keyword.lower()
        return [entity for entity in self.values() if keyword_lower in entity.content.lower()]

    def to_dict(self) -> Mapping[str, Mapping[str, object]]:
        return {entity_id: entity.to_dict() for entity_id, entity in self.items()}
