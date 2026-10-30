"""
TRUTHLINE — Contradiction Detector
===========================================================================
90% rules, 10% LLM.

THE FILTER IS THE POINT.
Without it, every claim pair would be sent to the LLM. With it, only pairs that
share a location AND have overlapping or adjacent time windows become
candidates. Everything else is classified `related` by rule — free and instant.

That is what keeps the LLM bill and latency bounded even when 30-50 reports
produce dozens of claims.
"""

from __future__ import annotations

from datetime import datetime
from itertools import combinations
from typing import Callable, Iterable

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import CONTRADICTION_TIME_WINDOW_MIN

__all__ = ["find_contradictions", "same_location", "times_overlap", "classify_pair"]

_RELATED = "related"
_SUPPORTS = "supports"
_CONTRADICTS = "contradicts"


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def same_location(a: dict, b: dict) -> bool:
    return (a.get("location") or "") == (b.get("location") or "")


def times_overlap(a: dict, b: dict, window_min: float = CONTRADICTION_TIME_WINDOW_MIN) -> bool:
    """True when two events are close enough in time to be comparable."""
    try:
        ta, tb = _ts(a["timestamp"]), _ts(b["timestamp"])
    except (KeyError, ValueError, TypeError):
        return False
    return abs((ta - tb).total_seconds()) / 60.0 <= window_min


def _texts_identical(a: dict, b: dict) -> bool:
    return (a.get("event") or "").strip().lower() == (b.get("event") or "").strip().lower()


def find_contradictions(
    claims: Iterable[dict],
    llm_classify: Callable[[dict, dict], str] | None = None,
    window_min: float = CONTRADICTION_TIME_WINDOW_MIN,
) -> list[dict]:
    """Compare every claim pair and return relations.

    Args:
        claims: report dicts (any shape carrying id/location/event/timestamp).
        llm_classify: optional callable(a, b) -> 'supports'|'contradicts'|'related'.
            When omitted, identical text is `supports`, differing text at the same
            place and time is `contradicts`, and everything else is `related`.
            Passing a classifier is what upgrades this from a stub to a real
            semantic check — "3 vehicles detected" vs "3 vehicles spotted" must
            NOT be flagged, and only the LLM can tell them apart.

    Returns:
        List of relation dicts with keys:
        claim_a, claim_b, relation_type, confidence, reason, classified_by
    """
    claims = list(claims)
    relations: list[dict] = []

    for a, b in combinations(claims, 2):
        if not same_location(a, b):
            continue  # different places are never comparable — rule, not LLM
        if not times_overlap(a, b, window_min):
            continue  # too far apart in time to conflict

        if _texts_identical(a, b):
            relations.append({
                "claim_a": a["id"], "claim_b": b["id"],
                "relation_type": _SUPPORTS,
                "confidence": 1.0,
                "reason": "identical wording at the same location and time",
                "classified_by": "rule",
            })
            continue

        if llm_classify is not None:
            kind = (llm_classify(a, b) or _RELATED).strip().lower()
            if kind not in {_SUPPORTS, _CONTRADICTS, _RELATED}:
                kind = _RELATED
            relations.append({
                "claim_a": a["id"], "claim_b": b["id"],
                "relation_type": kind,
                "confidence": None,
                "reason": "classified by LLM",
                "classified_by": "llm",
            })
        else:
            # No LLM available: a wording difference at the same place and time
            # is reported as a candidate contradiction rather than silently
            # dropped. The caller decides whether to escalate it.
            relations.append({
                "claim_a": a["id"], "claim_b": b["id"],
                "relation_type": _CONTRADICTS,
                "confidence": None,
                "reason": (
                    "differing wording at the same location and time "
                    "(unverified — no LLM classifier configured)"
                ),
                "classified_by": "rule",
            })

    return relations


def classify_pair(a: dict, b: dict) -> str:
    """Convenience wrapper for a single pair. Defaults to `related`."""
    return find_contradictions([a, b])[0]["relation_type"] if find_contradictions([a, b]) else _RELATED


if __name__ == "__main__":
    demo = [
        {"id": "B1", "source": "Drone-Alpha", "location": "Grid-9",
         "event": "5 vehicles moving north", "timestamp": "2026-09-18T14:59:00"},
        {"id": "B2", "source": "Ground-Charlie", "location": "Grid-9",
         "event": "No activity detected", "timestamp": "2026-09-18T15:00:00"},
        {"id": "A1", "source": "Drone-Alpha", "location": "Grid-7",
         "event": "3 vehicles detected", "timestamp": "2026-09-18T14:55:00"},
        {"id": "A2", "source": "Ground-Beta", "location": "Grid-7",
         "event": "3 vehicles detected", "timestamp": "2026-09-18T14:57:00"},
    ]
    print("=== Contradiction Detector (rule-only mode) ===\n")
    for r in find_contradictions(demo):
        print(f"  {r['claim_a']} vs {r['claim_b']}: {r['relation_type'].upper():12s} "
              f"[{r['classified_by']}] {r['reason']}")
