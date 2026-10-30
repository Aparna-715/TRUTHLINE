"""
TRUTHLINE — Evidence Gap Detector
===========================================================================
Deterministic rules only. No LLM.

The job is to say what the evidence is MISSING, not just what it contains.
That is requirement #4 of the five things that make TRUTHLINE an
evidence-integrity engine rather than a retrieval chatbot.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import MIN_SOURCES_FOR_CORROBORATION

__all__ = ["check_gaps", "detect_gaps"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_gaps(claims: Iterable[dict], detected_at: str | None = None) -> list[dict]:
    """Return one gap record per missing piece of evidence.

    A "claim" here is a report dict that already carries decay signals, i.e. the
    output of `agents.decay.batch_decay`.

    Rules (all deterministic):
      1. LOCATION THIN          fewer than MIN_SOURCES reports at that location
      2. NO CORROBORATION       a location backed by a single source
      3. NO RECENT SOURCE       every source at that location has decayed
      4. MISSING IDENTITY       the report text names no vehicle/unit identity
    """
    claims = list(claims)
    if not claims:
        return []

    by_location: dict[str, list[dict]] = {}
    for c in claims:
        by_location.setdefault(c.get("location", "UNKNOWN"), []).append(c)

    gaps: list[dict] = []
    stamp = detected_at or _now()

    for location, loc_claims in by_location.items():
        count = len(loc_claims)
        fresh = [c for c in loc_claims if not c.get("is_stale")]

        # Rule 1 + 2 — thin evidence
        if count < MIN_SOURCES_FOR_CORROBORATION:
            gaps.append({
                "claim_id": loc_claims[0].get("id", "unknown"),
                "location": location,
                "missing_attribute": "corroboration",
                "severity": "high",
                "suggested_verification": (
                    f"Only {count} source(s) at {location}; "
                    f"need {MIN_SOURCES_FOR_CORROBORATION}+ independent sources."
                ),
                "detected_at": stamp,
            })

        # Rule 3 — no source fresh enough to trust
        if loc_claims and not fresh:
            gaps.append({
                "claim_id": loc_claims[0].get("id", "unknown"),
                "location": location,
                "missing_attribute": "recent_source",
                "severity": "medium",
                "suggested_verification": (
                    f"All {count} source(s) at {location} have decayed below the "
                    f"usable freshness threshold. Request a new collection pass."
                ),
                "detected_at": stamp,
            })

        # Rule 4 — no identity in the report text
        for c in loc_claims:
            text = (c.get("event") or "").lower()
            has_identity = any(
                token in text
                for token in ("vehicle", "vehicles", "convoy", "personnel", "unit")
            )
            if not has_identity:
                gaps.append({
                    "claim_id": c.get("id", "unknown"),
                    "location": location,
                    "missing_attribute": "vehicle_id",
                    "severity": "medium",
                    "suggested_verification": (
                        f"Report {c.get('id')} states no vehicle or unit identity."
                    ),
                    "detected_at": stamp,
                })

    return gaps


# Alias — some callers read better with the longer name.
detect_gaps = check_gaps


if __name__ == "__main__":
    from agents.decay import batch_decay

    demo = [
        {"id": "D1", "source": "Satellite-2", "source_type": "satellite",
         "location": "Grid-12", "event": "Heat signatures detected",
         "timestamp": "2026-09-18T14:00:00"},
        {"id": "A1", "source": "Drone-Alpha", "source_type": "drone",
         "location": "Grid-7", "event": "3 vehicles detected",
         "timestamp": "2026-09-18T14:55:00"},
    ]
    print("=== Evidence Gap Detector ===\n")
    for g in check_gaps(batch_decay(demo, "2026-09-18T15:00:00")):
        print(f"  [{g['severity'].upper():6s}] {g['location']}: "
              f"{g['missing_attribute']} — {g['suggested_verification']}")
