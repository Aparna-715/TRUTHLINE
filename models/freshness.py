"""Freshness — the signature signal. Computed in code, never guessed by an LLM."""
from __future__ import annotations

from pydantic import BaseModel, Field

VALID_LABELS = frozenset({"FRESH", "AGING", "STALE", "EXPIRED"})


class FreshnessIn(BaseModel):
    """What the decay agent produces."""

    claim_id: str = Field(..., min_length=1)
    age_minutes: float = Field(..., ge=0.0)
    score: float = Field(..., ge=0.0, le=1.0)
    label: str
    scenario_time: str

    @property
    def is_stale(self) -> bool:
        return self.score < 0.1


class Freshness(FreshnessIn):
    """A stored freshness record."""

    computed_at: str | None = None
