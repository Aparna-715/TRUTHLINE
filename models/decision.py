"""Decision — the audit-trail record written by the Judge."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, field_validator

VALID_STATUS = frozenset({"SUPPORTED", "CONFLICTING", "STALE", "UNCERTAIN", "UPDATED"})


class DecisionIn(BaseModel):
    """What the Judge produces."""

    query: str = Field(..., min_length=1)
    status: str
    scenario_time: str
    rationale: str | None = None
    evaluated_claims: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    citation_violations: List[str] = Field(
        default_factory=list,
        description="Source IDs the LLM cited that retrieval never returned",
    )

    @field_validator("status")
    @classmethod
    def _normalise_status(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in VALID_STATUS:
            raise ValueError(f"status must be one of {sorted(VALID_STATUS)}, got {v!r}")
        return v


class Decision(DecisionIn):
    """A stored decision."""

    decision_id: int | None = None
    generated_at: str | None = None
