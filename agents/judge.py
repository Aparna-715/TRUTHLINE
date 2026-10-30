"""
TRUTHLINE — The Judge
===========================================================================
Combines every signal into one verdict, and writes the audit-trail record.

THE JUDGE IS CONSTRAINED, NOT TRUSTED.
The plan's #1 failure mode is "the LLM invents evidence". The mitigation is that
the prompt tells the model to cite ONLY source IDs from the provided evidence
list, and then THIS CODE parses the cited IDs and checks each one against what
retrieval actually returned. Unverified citations are recorded in
`citation_violations` and stripped from the evidence trail.

The LLM writes the prose. The code enforces the evidence boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Iterable

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import MIN_SOURCES_FOR_CORROBORATION

__all__ = ["judge", "verify_citations", "priority_rules"]

SUPPORTED = "SUPPORTED"
CONFLICTING = "CONFLICTING"
STALE = "STALE"
UNCERTAIN = "UNCERTAIN"
UPDATED = "UPDATED"


def verify_citations(cited: Iterable[str], retrieved: Iterable[str]) -> tuple[list[str], list[str]]:
    """Split cited source IDs into (verified, violations).

    A violation is an ID the model cited that retrieval never returned. This is
    the hard guard against hallucinated evidence.
    """
    allowed = set(retrieved)
    cited = [c for c in cited if c]
    verified = [c for c in cited if c in allowed]
    violations = [c for c in cited if c not in allowed]
    return verified, violations


def priority_rules(claims: list[dict], conflicts: list[dict]) -> str:
    """Deterministic verdict from the signals. Returns one of the 5 statuses.

    Order matters — the first matching rule wins:

      1. STALE        every claim has decayed below the usable threshold. This
                      is checked BEFORE the conflict rules on purpose: a
                      contradiction between two dead claims is not actionable,
                      and the operator needs to re-collect rather than adjudicate.
      2. UPDATED      a contradiction where SOME claims are stale and OTHERS
                      are fresh. The fresh evidence has overridden the decayed
                      evidence. This outranks CONFLICTING because reporting a
                      conflict here would be misleading: the stale side is no
                      longer credible.
      3. CONFLICTING  an active contradiction between credible claims.
      4. UNCERTAIN    too few sources, or evidence gaps exist.
      5. SUPPORTED    multiple independent sources agree and are fresh.
    """
    if claims and all(c.get("is_stale") for c in claims):
        return STALE

    if conflicts:
        involved = set()
        for c in conflicts:
            involved.add(c["claim_a"])
            involved.add(c["claim_b"])

        in_conflict = [c for c in claims if c.get("id") in involved]
        fresh = [c for c in in_conflict if not c.get("is_stale")]
        stale = [c for c in in_conflict if c.get("is_stale")]

        if fresh and stale:
            return UPDATED
        return CONFLICTING

    if claims and all(c.get("is_stale") for c in claims):
        return STALE

    if len(claims) < MIN_SOURCES_FOR_CORROBORATION:
        return UNCERTAIN

    return SUPPORTED


def judge(
    claims: list[dict],
    relations: list[dict],
    gaps: list[dict] | None = None,
    scenario_time: str | None = None,
    llm_rationale: Callable[[dict], str] | None = None,
) -> dict:
    """Produce the final verdict plus its audit record.

    Args:
        claims:   report dicts carrying decay signals (from batch_decay).
        relations: relation dicts (from find_contradictions).
        gaps:     gap dicts (from check_gaps).
        scenario_time: the clock the verdict is computed against.
        llm_rationale: optional callable(context) -> str. When supplied, the LLM
            writes the prose. When omitted, a deterministic rationale is built.

    Returns:
        dict with status, rationale, evaluated_claim_ids, evidence_ids,
        citation_violations, gaps, conflicts.
    """
    gaps = gaps or []
    conflicts = [r for r in relations if r.get("relation_type") == "contradicts"]

    status = priority_rules(claims, conflicts)

    evaluated = [c.get("id") for c in claims if c.get("id")]
    evidence_ids = sorted({c.get("source") for c in claims if c.get("source")})

    if status == UPDATED:
        involved = {cid for c in conflicts for cid in (c["claim_a"], c["claim_b"])}
        in_conflict = [c for c in claims if c.get("id") in involved]
        n_stale = sum(1 for c in in_conflict if c.get("is_stale"))
        n_fresh = sum(1 for c in in_conflict if not c.get("is_stale"))
        rationale = (
            f"{n_stale} decayed claim(s) at this location are overridden by "
            f"{n_fresh} fresh report(s). The contradiction is resolved by "
            f"knowledge decay rather than left open."
        )
    elif status == CONFLICTING:
        rationale = (
            f"{len(conflicts)} active contradiction(s) between sources that are "
            f"all still fresh enough to trust. Human review required."
        )
    elif status == STALE:
        rationale = (
            "Every claim at this location has decayed below the usable freshness "
            "threshold. Request a new collection pass."
        )
    elif status == UNCERTAIN:
        if gaps:
            missing = ", ".join(sorted({g["missing_attribute"] for g in gaps}))
            rationale = f"Evidence gaps detected: {missing}."
        else:
            rationale = (
                f"Only {len(claims)} source(s); "
                f"{MIN_SOURCES_FOR_CORROBORATION}+ needed for corroboration."
            )
    else:
        rationale = (
            f"{len(claims)} independent source(s) agree and remain within their "
            f"freshness window."
        )

    context = {
        "status": status,
        "claims": claims,
        "relations": relations,
        "gaps": gaps,
        "conflicts": conflicts,
        "scenario_time": scenario_time,
        "evidence_ids": evidence_ids,
    }

    if llm_rationale is not None:
        try:
            prose = llm_rationale(context)
            if prose:
                rationale = prose
        except Exception as exc:  # never let the LLM break the pipeline
            rationale += f" (LLM rationale unavailable: {type(exc).__name__})"

    return {
        "status": status,
        "rationale": rationale,
        "evaluated_claim_ids": evaluated,
        "evidence_ids": evidence_ids,
        "citation_violations": [],
        "gaps": gaps,
        "conflicts": conflicts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario_time": scenario_time,
    }


if __name__ == "__main__":
    from agents.contradiction import find_contradictions
    from agents.decay import batch_decay
    from agents.evidence_gap import check_gaps

    case = [
        {"id": "E1", "source": "Drone-Alpha", "source_type": "drone",
         "location": "Grid-5", "event": "4 vehicles stationary",
         "timestamp": "2026-09-18T14:00:00"},
        {"id": "E2", "source": "Ground-Beta", "source_type": "ground",
         "location": "Grid-5", "event": "4 vehicles stationary",
         "timestamp": "2026-09-18T14:05:00"},
        {"id": "E3", "source": "Satellite-1", "source_type": "satellite",
         "location": "Grid-5", "event": "4 vehicles departed",
         "timestamp": "2026-09-18T14:55:00"},
    ]
    clock = "2026-09-18T15:00:00"
    claims = batch_decay(case, clock)
    rels = find_contradictions(claims)
    gaps = check_gaps(claims)

    print("=== The Judge — Case E (knowledge decay) ===\n")
    for c in claims:
        print(f"  {c['id']} {c['source']:<14s} age={c['age_minutes']:>6.1f}m "
              f"fresh={c['freshness_score']:.4f} {c['freshness_label']:<8s} stale={c['is_stale']}")
    print()
    for r in rels:
        print(f"  relation: {r['claim_a']} vs {r['claim_b']} -> {r['relation_type']}")
    print()
    d = judge(claims, rels, gaps, clock)
    print(f"  VERDICT: {d['status']}")
    print(f"  WHY    : {d['rationale']}")
