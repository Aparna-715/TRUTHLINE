"""Relation — the edge between two claims in the evidence graph."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

VALID_RELATION_TYPES = frozenset({"supports", "contradicts", "related"})


class RelationIn(BaseModel):
    """What the contradiction agent produces."""

    claim_a: str = Field(..., min_length=1)
    claim_b: str = Field(..., min_length=1)
    relation_type: str
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    reason: str | None = None
    classified_by: str | None = Field(
        None, description="'rule' for deterministic, 'llm' for model-classified"
    )

    @field_validator("relation_type")
    @classmethod
    def _normalise_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_RELATION_TYPES:
            raise ValueError(
                f"relation_type must be one of {sorted(VALID_RELATION_TYPES)}, got {v!r}"
            )
        return v

    @field_validator("classified_by")
    @classmethod
    def _normalise_by(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        if v not in {"rule", "llm"}:
            raise ValueError("classified_by must be 'rule' or 'llm'")
        return v


class Relation(RelationIn):
    """A stored relation."""

    relation_id: int | None = None
    created_at: str | None = None

    @property
    def is_conflict(self) -> bool:
        return self.relation_type == "contradicts"
