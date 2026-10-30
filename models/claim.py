"""Claim — the structured unit of evidence. NOT a retrieved text chunk."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import TAU, BAND_FRESH, BAND_AGING, STALE_THRESHOLD

VALID_SOURCE_TYPES = frozenset(TAU.keys())


class ClaimIn(BaseModel):
    """What the extraction agent produces."""

    claim_id: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    source_type: str
    location: str = Field(..., min_length=1)
    event_time: str = Field(..., description="ISO 8601")
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    extraction_confidence: float | None = Field(None, ge=0.0, le=1.0)

    @field_validator("source_type")
    @classmethod
    def _normalise_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"source_type must be one of {sorted(VALID_SOURCE_TYPES)}, got {v!r}"
            )
        return v


class Claim(ClaimIn):
    """A stored claim, optionally enriched with computed decay signals."""

    extracted_at: str | None = None
    age_minutes: float | None = None
    freshness_score: float | None = None
    freshness_label: str | None = None

    @property
    def is_stale(self) -> bool:
        """True when the claim has decayed below the usable threshold."""
        if self.freshness_score is None:
            return False
        return self.freshness_score < STALE_THRESHOLD

    def with_freshness(self, score: float, label: str, age: float) -> "Claim":
        """Return a copy carrying decay signals. Keeps the model immutable-ish."""
        return self.model_copy(
            update={
                "freshness_score": score,
                "freshness_label": label,
                "age_minutes": age,
            }
        )


def label_for_score(score: float) -> str:
    """Band a 0.0-1.0 freshness score into a human label."""
    if score > BAND_FRESH:
        return "FRESH"
    if score > BAND_AGING:
        return "AGING"
    if score > STALE_THRESHOLD:
        return "STALE"
    return "EXPIRED"
