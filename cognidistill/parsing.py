"""Utilities for parsing raw text into knowledge entities."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence

from .entities import KnowledgeEntity

SENTENCE_REGEX = re.compile(r"(?<=[.!?])\s+")

# Keywords per entity type for naive classification
ENTITY_KEYWORDS = {
    "prozess": ["prozess", "ablauf", "schritt", "workflow", "pipeline"],
    "relation": ["zwischen", "beziehung", "relati", "abhängig"],
    "methode": ["methode", "technik", "vorgehen", "strategie"],
    "fakt": ["ist", "sind", "beträgt", "besteht", "wird"],
}


def split_into_sentences(text: str) -> List[str]:
    """Return a list of sentences using a simple rule-based splitter."""

    text = text.strip()
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def guess_entity_type(sentence: str, default: str = "konzept") -> str:
    """Guess an entity type based on keyword occurrences."""

    sentence_lower = sentence.lower()
    for entity_type, keywords in ENTITY_KEYWORDS.items():
        if any(keyword in sentence_lower for keyword in keywords):
            return entity_type
    return default


def estimate_confidence(sentence: str) -> float:
    """Estimate a confidence score for a sentence."""

    length = len(sentence)
    if length < 40:
        base = 0.65
    elif length < 120:
        base = 0.75
    else:
        base = 0.85

    evidence_markers = ["studie", "daten", "experiment", "analyse"]
    if any(marker in sentence.lower() for marker in evidence_markers):
        base = min(1.0, base + 0.1)
    return base


def extract_entities(text: str, *, sources: Optional[Sequence[str]] = None) -> List[KnowledgeEntity]:
    """Parse text and create knowledge entities."""

    sentences = split_into_sentences(text)
    if not sentences:
        return []

    now = datetime.now(timezone.utc)
    source_list = list(sources) if sources else ["unbekannt"]
    entities: List[KnowledgeEntity] = []

    for sentence in sentences:
        entity_type = guess_entity_type(sentence)
        confidence = estimate_confidence(sentence)
        entity_id = KnowledgeEntity.generate_id(sentence, entity_type)
        entity = KnowledgeEntity(
            entity_id=entity_id,
            entity_type=entity_type,
            content=sentence,
            confidence=confidence,
            sources=source_list.copy(),
            created=now,
            updated=now,
            version=1,
        )
        entities.append(entity)

    _link_entities(entities)
    return entities


def _link_entities(entities: Iterable[KnowledgeEntity]) -> None:
    """Apply naive relationship detection between entities."""

    entity_list = list(entities)
    for source in entity_list:
        if source.entity_type != "relation":
            continue
        for target in entity_list:
            if target is source:
                continue
            if _mentions(source.content, target.content):
                source.add_relationship("verweist_auf", target.entity_id)


def _mentions(sentence: str, other_sentence: str) -> bool:
    """Return True if significant words overlap."""

    source_tokens = _tokenise(sentence)
    other_tokens = _tokenise(other_sentence)
    overlap = source_tokens & other_tokens
    return len(overlap) >= 2


def _tokenise(text: str) -> set[str]:
    tokens = re.findall(r"[\wäöüÄÖÜß-]+", text.lower())
    return {token for token in tokens if len(token) > 3}
