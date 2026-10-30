"""Source record — one raw intelligence report, before extraction."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import TAU

VALID_SOURCE_TYPES = frozenset(TAU.keys())


class SourceIn(BaseModel):
    """What the ingestion agent accepts."""

    source_id: str = Field(..., min_length=1, description="Stable unique id, e.g. 'A1'")
    source_type: str = Field(..., description="drone | ground | satellite | intel")
    text: str = Field(..., min_length=1)
    source_name: str | None = None
    location: str | None = None
    timestamp: str | None = None          # ISO 8601
    reliability_class: str | None = None

    @field_validator("source_type")
    @classmethod
    def _normalise_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"source_type must be one of {sorted(VALID_SOURCE_TYPES)}, got {v!r}"
            )
        return v


class Source(SourceIn):
    """A stored source. `timestamp` is required once persisted."""

    timestamp: str
    ingested_at: str | None = None

    def payload(self) -> dict:
        """The Qdrant payload — mirrors the retrieval filter fields."""
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "location": self.location,
            "timestamp": self.timestamp,
            "reliability_class": self.reliability_class,
        }
