"""
TRUTHLINE — Synthetic dataset generator (Operation NORTHSTAR)
===========================================================================
Produces the demo data AND the evaluation harness in one shot.

Outputs
-------
data/northstar_reports.json   Raw source records (what the real pipeline ingests).
                              NO computed fields — freshness is always computed
                              at runtime, never stored.
data/test_cases.json          The 5 labelled cases with expected verdicts.
data/case_<x>.json            Per-case fixtures (backward compatible with the
                              existing React UI demo).

IMPORTANT
---------
Freshness is a DERIVED signal. It must never be baked into a data file — if it
is, the value goes stale the moment the scenario time moves, which is exactly
what Case E is supposed to demonstrate.

Run:  python3 data/generate.py
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DATA_DIR, TAU  # noqa: E402

# ── Scenario clock ─────────────────────────────────────────────────────
# Every age in the dataset is measured backwards from this moment.
SCENARIO_TIME = datetime(2026, 9, 18, 15, 0, 0)

SOURCE_NAMES = {
    "drone": ["Drone-Alpha", "Drone-Bravo", "Drone-Charlie"],
    "ground": ["Ground-Beta", "Ground-Charlie", "Ground-Delta"],
    "satellite": ["Satellite-1", "Satellite-2"],
    "intel": ["Intel-Desk", "SIGINT-Unit"],
}

GRIDS = [f"Grid-{n}" for n in range(1, 21)]


def age_minutes(ts: datetime) -> float:
    """Age of a timestamp relative to the scenario clock."""
    return round((SCENARIO_TIME - ts).total_seconds() / 60.0, 1)


def make_report(
    rid: str,
    source_type: str,
    location: str,
    event: str,
    ts: datetime,
    source_name: str | None = None,
) -> dict:
    """Build one raw source record.

    Deliberately carries NO derived fields. `age_minutes` and `freshness_score`
    are computed at runtime from `timestamp` against the scenario clock — if
    they were stored here, advancing the clock would change nothing and the
    knowledge-decay demo would not work.
    """
    return {
        "id": rid,
        "source": source_name or random.choice(SOURCE_NAMES[source_type]),
        "source_type": source_type,
        "location": location,
        "event": event,
        "timestamp": ts.isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════
# THE 5 LABELLED TEST CASES — injected deliberately
# ═══════════════════════════════════════════════════════════════════════

def case_a() -> dict:
    """3 independent sources agree -> SUPPORTED."""
    return {
        "case_id": "A",
        "name": "SUPPORTED",
        "description": "Three independent sources report the same event at the same location.",
        "expected_verdict": "supported",
        "reports": [
            make_report("A1", "drone", "Grid-7", "3 vehicles detected",
                        SCENARIO_TIME - timedelta(minutes=5), "Drone-Alpha"),
            make_report("A2", "ground", "Grid-7", "3 vehicles detected",
                        SCENARIO_TIME - timedelta(minutes=3), "Ground-Beta"),
            make_report("A3", "satellite", "Grid-7", "3 vehicles detected",
                        SCENARIO_TIME - timedelta(minutes=4), "Satellite-1"),
        ],
    }


def case_b() -> dict:
    """Two fresh sources disagree -> CONFLICTING."""
    return {
        "case_id": "B",
        "name": "CONFLICTING",
        "description": "Two sources report opposite things at the same location.",
        "expected_verdict": "conflicting",
        "reports": [
            make_report("B1", "drone", "Grid-9", "5 vehicles moving north",
                        SCENARIO_TIME - timedelta(minutes=1), "Drone-Alpha"),
            make_report("B2", "ground", "Grid-9", "No activity detected",
                        SCENARIO_TIME - timedelta(minutes=2), "Ground-Charlie"),
        ],
    }


def case_c() -> dict:
    """Everything is 6+ hours old -> STALE."""
    return {
        "case_id": "C",
        "name": "STALE",
        "description": "All reports are from 6+ hours ago. Evidence has decayed to zero.",
        "expected_verdict": "stale",
        "reports": [
            make_report("C1", "drone", "Grid-3", "2 vehicles parked",
                        SCENARIO_TIME - timedelta(hours=7), "Drone-Alpha"),
            make_report("C2", "ground", "Grid-3", "2 vehicles parked",
                        SCENARIO_TIME - timedelta(hours=6, minutes=45), "Ground-Beta"),
        ],
    }


def case_d() -> dict:
    """One source only, no corroboration -> UNCERTAIN."""
    return {
        "case_id": "D",
        "name": "INSUFFICIENT",
        "description": "Only one source reports an event. No corroboration.",
        "expected_verdict": "uncertain",
        "reports": [
            make_report("D1", "satellite", "Grid-12", "Heat signatures detected",
                        SCENARIO_TIME - timedelta(hours=1), "Satellite-2"),
        ],
    }


def case_e() -> dict:
    """A fresh report overrides stale ones -> UPDATED.

    This is the knowledge-decay demo. The two older reports say the vehicles
    are still there; the fresh satellite pass says they departed. Because the
    contradicting claims have decayed, the verdict is UPDATED, not CONFLICTING.
    """
    return {
        "case_id": "E",
        "name": "UPDATE",
        "description": "Newer satellite report overrides older drone/ground reports.",
        "expected_verdict": "updated",
        "reports": [
            make_report("E1", "drone", "Grid-5", "4 vehicles stationary",
                        SCENARIO_TIME - timedelta(hours=1), "Drone-Alpha"),
            make_report("E2", "ground", "Grid-5", "4 vehicles stationary",
                        SCENARIO_TIME - timedelta(minutes=55), "Ground-Beta"),
            make_report("E3", "satellite", "Grid-5", "4 vehicles departed",
                        SCENARIO_TIME - timedelta(minutes=5), "Satellite-1"),
        ],
    }


# ═══════════════════════════════════════════════════════════════════════
# FILLER REPORTS — bulk out the corpus so retrieval has something to do
# ═══════════════════════════════════════════════════════════════════════

def filler_reports(n: int = 40, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    events = [
        "{n} vehicles detected", "{n} vehicles moving north", "{n} vehicles stationary",
        "No activity detected", "Heat signatures detected", "{n} personnel observed",
        "Convoy sighted", "Position abandoned",
    ]
    reports = []
    for i in range(n):
        stype = rng.choice(list(TAU.keys()))
        grid = rng.choice(GRIDS)
        age = rng.uniform(2, 300)  # minutes
        ts = SCENARIO_TIME - timedelta(minutes=age)
        event = rng.choice(events).format(n=rng.randint(1, 8))
        reports.append(make_report(f"F{i + 1:03d}", stype, grid, event, ts))
    return reports


# ═══════════════════════════════════════════════════════════════════════
# WRITE
# ═══════════════════════════════════════════════════════════════════════

def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    cases = [case_a(), case_b(), case_c(), case_d(), case_e()]
    filler = filler_reports()

    # 1. Raw corpus — sources only, no derived fields
    corpus = {
        "scenario_time": SCENARIO_TIME.isoformat(),
        "tau": TAU,
        "source_count": len(filler),
        "reports": filler,
    }
    (DATA_DIR / "northstar_reports.json").write_text(
        json.dumps(corpus, indent=2), encoding="utf-8"
    )

    # 2. Labelled test cases — the evaluation harness
    test_cases = {
        "scenario_time": SCENARIO_TIME.isoformat(),
        "cases": {c["case_id"]: c for c in cases},
    }
    (DATA_DIR / "test_cases.json").write_text(
        json.dumps(test_cases, indent=2), encoding="utf-8"
    )

    # 3. Per-case fixtures (backward compatible with the existing UI)
    for c in cases:
        fname = DATA_DIR / f"case_{c['case_id'].lower()}_{c['name'].lower()}.json"
        fname.write_text(json.dumps(c, indent=2), encoding="utf-8")

    print("TRUTHLINE dataset generated")
    print(f"  scenario time : {SCENARIO_TIME.isoformat()}")
    print(f"  corpus        : {len(filler)} reports -> data/northstar_reports.json")
    print(f"  test cases    : {len(cases)} labelled  -> data/test_cases.json")
    for c in cases:
        print(f"    case {c['case_id']} {c['name']:<12s} "
              f"expected={c['expected_verdict']:<11s} reports={len(c['reports'])}")
    print(f"  fixtures      : data/case_*.json")
    print()
    print("  NOTE: no freshness_score is stored in any file — it is computed at runtime.")


if __name__ == "__main__":
    main()
