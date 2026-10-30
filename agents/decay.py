"""
TRUTHLINE — Knowledge Decay Engine
===========================================================================
The signature feature. Pure maths, no LLM.

    freshness = e ^ (-age / tau)

      age = how old the evidence is, in MINUTES
      tau = how long that source type stays fresh, in MINUTES

    Result: 0.0 (dead) to 1.0 (brand new).

Why this matters: it is the one signal in TRUTHLINE that is computed in code
and shown in the UI, rather than being folded into an LLM's judgement. That is
what separates an evidence-integrity engine from a RAG chatbot.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import BAND_AGING, BAND_FRESH, DEFAULT_TAU, STALE_THRESHOLD, TAU

# Re-exported so callers can import the bands from one place.
__all__ = [
    "TAU",
    "STALE_THRESHOLD",
    "calculate_freshness",
    "is_stale",
    "get_freshness_label",
    "age_from_timestamps",
    "batch_decay",
]


def calculate_freshness(age_minutes: float, source_type: str) -> float:
    """Freshness score for one piece of evidence.

    Args:
        age_minutes: age of the evidence in minutes. Negative ages are clamped
            to 0 — a report cannot be "from the future", and without the clamp
            the exponential returns a value ABOVE 1.0, which is impossible.
        source_type: drone | ground | satellite | intel

    Returns:
        Float in 0.0 - 1.0 inclusive.
    """
    age = max(0.0, float(age_minutes))
    tau = TAU.get(source_type, DEFAULT_TAU)
    if tau <= 0:
        return 1.0 if age == 0 else 0.0
    return round(min(1.0, math.exp(-age / tau)), 4)


def is_stale(freshness_score: float, threshold: float = STALE_THRESHOLD) -> bool:
    """True when a score has decayed below the usable threshold."""
    return freshness_score < threshold


def get_freshness_label(freshness_score: float) -> str:
    """Band a score into a human label."""
    if freshness_score > BAND_FRESH:
        return "FRESH"
    if freshness_score > BAND_AGING:
        return "AGING"
    if freshness_score > STALE_THRESHOLD:
        return "STALE"
    return "EXPIRED"


def age_from_timestamps(event_time: str | datetime, scenario_time: str | datetime) -> float:
    """Age in minutes of an event relative to the scenario clock.

    Accepts ISO strings or datetimes so callers can pass either.

    Mixed awareness is a real hazard here: reports ingested with `now()` carry a
    UTC offset ("...+00:00"), while fixtures and operator-entered times are naive
    local ("2026-09-18T14:55:00"). Subtracting an aware datetime from a naive one
    raises TypeError, which used to surface as a 500 from /area.

    Both values are wall-clock readings of the same operation and the decay
    formula only cares about their difference, so when exactly one side carries
    tzinfo we drop it from both.
    """
    if isinstance(event_time, str):
        event_time = datetime.fromisoformat(event_time)
    if isinstance(scenario_time, str):
        scenario_time = datetime.fromisoformat(scenario_time)

    if (event_time.tzinfo is None) != (scenario_time.tzinfo is None):
        event_time = event_time.replace(tzinfo=None)
        scenario_time = scenario_time.replace(tzinfo=None)

    return round((scenario_time - event_time).total_seconds() / 60.0, 1)


def batch_decay(
    reports: Iterable[dict],
    scenario_time: str | datetime,
) -> list[dict]:
    """Attach decay signals to a list of report dicts.

    Each report needs `source_type` and `timestamp`. Age is ALWAYS computed from
    the timestamp against `scenario_time` when a timestamp is present — a stored
    `age_minutes` field is only used as a fallback for records that have no
    timestamp at all.

    That ordering is what makes the knowledge-decay demo work: advancing
    `scenario_time` must change the scores. If a stale age were read from the
    record instead, moving the clock would do nothing.

    Adds: age_minutes, freshness_score, freshness_label, is_stale
    """
    out = []
    for r in reports:
        item = dict(r)
        ts = item.get("timestamp")

        if scenario_time is not None and ts:
            age = age_from_timestamps(ts, scenario_time)
        elif item.get("age_minutes") is not None:
            age = float(item["age_minutes"])
        elif ts:
            age = age_from_timestamps(ts, scenario_time)
        else:
            age = 0.0

        score = calculate_freshness(age, item["source_type"])
        item["age_minutes"] = round(age, 1)
        item["freshness_score"] = score
        item["freshness_label"] = get_freshness_label(score)
        item["is_stale"] = is_stale(score)
        out.append(item)
    return out


# ── Quick self-test ──
if __name__ == "__main__":
    print("=== TRUTHLINE Knowledge Decay Engine ===")
    print(f"tau = {TAU}   stale below {STALE_THRESHOLD}\n")

    for age, stype, desc in [
        (0, "drone", "Drone report, brand new"),
        (1, "drone", "Drone report, 1 min old"),
        (5, "drone", "Drone report, 5 min old"),
        (30, "drone", "Drone report, 30 min old"),
        (15, "ground", "Ground report, 15 min old"),
        (60, "satellite", "Satellite image, 1 hour old"),
        (120, "intel", "Intel doc, 2 hours old"),
        (-2, "ground", "NEGATIVE age (must clamp to 0)"),
    ]:
        score = calculate_freshness(age, stype)
        print(f"  {desc:<36s} age={age:>6.1f}  freshness={score:.4f} "
              f"({get_freshness_label(score)})  stale={is_stale(score)}")

    # Regression guard for the negative-age bug
    assert calculate_freshness(-2, "ground") <= 1.0, "freshness must never exceed 1.0"
    assert calculate_freshness(-2, "ground") == 1.0, "negative age should clamp to brand new"
    print("\n  clamp check: negative age -> 1.0  OK")
