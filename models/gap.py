"""Gap — what the evidence is MISSING. Deterministic rules, no LLM."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

VALID_SEVERITY = frozenset({"low", "medium", "high"})


class GapIn(BaseModel):
    """What the evidence-gap agent produces."""

    claim_id: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    missing_attribute: str = Field(
        ..., description="e.g. vehicle_id | corroboration | location"
    )
    severity: str = "medium"
    suggested_verification: str | None = None

    @field_validator("severity")
    @classmethod
    def _normalise_severity(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_SEVERITY:
            raise ValueError(f"severity must be one of {sorted(VALID_SEVERITY)}")
        return v


class Gap(GapIn):
    """A stored gap."""

    gap_id: int | None = None
    detected_at: str | None = None
