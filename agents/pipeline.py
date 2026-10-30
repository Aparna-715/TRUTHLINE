"""
TRUTHLINE — Pipeline orchestrator
===========================================================================
This is the module that REPLACES the old `run_pipeline()` simulator that lived
inside agents/pipeline.py.

It calls the real agents in order and returns one result dict. The UI and the
test harness both call this, so there is exactly one definition of "what a
TRUTHLINE investigation is".

    reports -> decay -> contradiction -> gaps -> judge -> verdict

Design notes
------------
* Degrades gracefully. If Qdrant or the LLM is unavailable the deterministic
  agents still run; only the LLM-classified relations fall back to rules.
* Never raises on bad input. A pipeline that crashes during a demo is worse
  than one that returns a partial answer.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.contradiction import find_contradictions  # noqa: E402
from agents.decay import batch_decay  # noqa: E402
from agents.evidence_gap import check_gaps  # noqa: E402
from agents.judge import judge  # noqa: E402
from config import DATA_DIR, SCENARIO_TIME  # noqa: E402

__all__ = ["investigate", "load_case", "load_all_cases", "run_all_cases"]


def load_case(case_id: str) -> dict:
    """Load one labelled case fixture from data/."""
    import json

    for path in sorted(DATA_DIR.glob("case_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("case_id", "").upper() == case_id.upper():
            return data
    raise KeyError(f"No case fixture found for id {case_id!r}")


def load_all_cases() -> dict[str, dict]:
    """Load every case fixture, keyed by case id."""
    import json

    cases: dict[str, dict] = {}
    for path in sorted(DATA_DIR.glob("case_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        cases[data["case_id"]] = data
    return cases


def investigate(
    case: dict,
    scenario_time: str | None = None,
    llm_classify=None,
    llm_rationale=None,
) -> dict:
    """Run the full pipeline over one case.

    Args:
        case: a case dict with a `reports` list.
        scenario_time: ISO timestamp to compute decay against. Defaults to the
            newest report timestamp — i.e. "as of the latest intelligence".
        llm_classify: optional callable(a, b) -> relation_type, used to upgrade
            contradiction detection from string comparison to semantics.
        llm_rationale: optional callable(context) -> prose for the Judge.

    Returns:
        dict with claims, relations, gaps, freshness, verdict, rationale,
        evidence_ids, summary.
    """
    reports = list(case.get("reports", []))
    if not reports:
        return {
            "case_id": case.get("case_id"),
            "claims": [], "relations": [], "gaps": [], "freshness": [],
            "verdict": "UNCERTAIN",
            "rationale": "No reports were supplied for this case.",
            "evidence_ids": [],
            "summary": {},
        }

    if scenario_time is None:
        scenario_time = SCENARIO_TIME

    # Agent 4 (decay) — always runs, it is pure maths
    claims = batch_decay(reports, scenario_time)

    # Agent 3 (contradiction) — rules first, LLM only for candidate pairs
    relations = find_contradictions(claims, llm_classify=llm_classify)

    # Agent 5 (gaps) — deterministic rules
    gaps = check_gaps(claims)

    # Agent 6 (judge) — deterministic priority rules, optional LLM prose
    decision = judge(claims, relations, gaps, scenario_time, llm_rationale=llm_rationale)

    fresh_scores = [c["freshness_score"] for c in claims]
    summary = {
        "total_claims": len(claims),
        "total_relations": len(relations),
        "total_contradictions": sum(
            1 for r in relations if r.get("relation_type") == "contradicts"
        ),
        "total_supports": sum(
            1 for r in relations if r.get("relation_type") == "supports"
        ),
        "total_gaps": len(gaps),
        "stale_count": sum(1 for c in claims if c.get("is_stale")),
        "avg_freshness": round(sum(fresh_scores) / len(fresh_scores), 4) if fresh_scores else 0.0,
        "locations_checked": len({c["location"] for c in claims}),
        "scenario_time": scenario_time,
        "expected_verdict": case.get("expected_verdict"),
    }

    return {
        "case_id": case.get("case_id"),
        "case_name": case.get("name"),
        "claims": claims,
        "relations": relations,
        "gaps": gaps,
        "freshness": [
            {
                "claim_id": c["id"],
                "age_minutes": c["age_minutes"],
                "score": c["freshness_score"],
                "label": c["freshness_label"],
            }
            for c in claims
        ],
        "verdict": decision["status"],
        "rationale": decision["rationale"],
        "evidence_ids": decision["evidence_ids"],
        "citation_violations": decision["citation_violations"],
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def run_all_cases(scenario_time: str | None = None) -> dict[str, dict]:
    """Run every labelled case. Returns {case_id: result}."""
    return {
        cid: investigate(case, scenario_time=scenario_time)
        for cid, case in load_all_cases().items()
    }


if __name__ == "__main__":
    print("=== TRUTHLINE pipeline — all cases ===\n")
    results = run_all_cases()
    for cid, r in results.items():
        s = r["summary"]
        expected = (s.get("expected_verdict") or "").upper()
        actual = r["verdict"]
        mark = "OK " if expected == actual else "XX "
        print(f"  {mark}case {cid} {r['case_name']:<12s} "
              f"expected={expected:<11s} got={actual:<11s} "
              f"claims={s['total_claims']} conflicts={s['total_contradictions']} "
              f"avg_fresh={s['avg_freshness']:.3f}")
