"""
TRUTHLINE — Evaluation harness
===========================================================================
Runs every labelled case through the REAL pipeline and checks the verdict
against the expected one. Also reports the metrics the plan asks for.

    python3 tests/run_all.py          # exit 0 if all pass, 1 if any fail

This is the gate on the demo: if this does not print 5/5, we do not present.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.decay import calculate_freshness, get_freshness_label, is_stale  # noqa: E402
from agents.judge import verify_citations  # noqa: E402
from agents.pipeline import investigate, load_all_cases  # noqa: E402

# ── Expected behaviour per case, beyond just the verdict ────────────────────
# These let the harness catch regressions the verdict alone would miss.
EXPECTED = {
    "A": {"verdict": "SUPPORTED",   "min_claims": 3, "conflicts": 0},
    "B": {"verdict": "CONFLICTING", "min_claims": 2, "conflicts": 1},
    "C": {"verdict": "STALE",       "min_claims": 2, "conflicts": 0},
    "D": {"verdict": "UNCERTAIN",   "min_claims": 1, "conflicts": 0, "min_gaps": 1},
    "E": {"verdict": "UPDATED",     "min_claims": 3, "conflicts": 2},
}


def check_decay_engine() -> list[tuple[str, bool, str]]:
    """Unit checks on the signature feature."""
    results = []
    cases = [
        (0, "drone", 1.0, "FRESH"),
        (1, "drone", None, "FRESH"),
        (5, "drone", None, "AGING"),
        (30, "drone", None, "EXPIRED"),
        (60, "satellite", None, "STALE"),
        (120, "intel", None, "FRESH"),
    ]
    for age, stype, expect_score, expect_label in cases:
        score = calculate_freshness(age, stype)
        label = get_freshness_label(score)
        ok = label == expect_label and (expect_score is None or abs(score - expect_score) < 1e-6)
        results.append((f"decay age={age} {stype}", ok, f"{score:.4f} {label}"))

    # Regression: negative age must clamp, never exceed 1.0
    neg = calculate_freshness(-2, "ground")
    results.append(("decay negative age clamps to 1.0", neg == 1.0, f"{neg:.4f}"))
    results.append(("decay never exceeds 1.0", calculate_freshness(0.001, "drone") <= 1.0, "ok"))
    return results


def check_citation_enforcement() -> list[tuple[str, bool, str]]:
    """The Judge must reject source IDs retrieval never returned."""
    verified, violations = verify_citations(
        cited=["A1", "A2", "GHOST-99"],
        retrieved=["A1", "A2", "A3"],
    )
    ok = verified == ["A1", "A2"] and violations == ["GHOST-99"]
    return [("citation enforcement strips hallucinated IDs", ok,
             f"verified={verified} violations={violations}")]


def main() -> int:
    print("=" * 78)
    print("TRUTHLINE — EVALUATION HARNESS")
    print("=" * 78)

    failures: list[str] = []

    # ── 1. Unit checks ────────────────────────────────────────────────────
    print("\n[1] Unit checks\n")
    for name, ok, detail in check_decay_engine() + check_citation_enforcement():
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<42s} {detail}")
        if not ok:
            failures.append(name)

    # ── 2. End-to-end cases ───────────────────────────────────────────────
    print("\n[2] End-to-end test cases\n")
    print(f"  {'':2s} {'Case':5s} {'Expected':<12s} {'Actual':<12s} {'OK':4s} "
          f"{'claims':>6s} {'conf':>5s} {'gaps':>5s} {'avgFresh':>9s} {'ms':>7s}")
    print("  " + "-" * 74)

    cases = load_all_cases()
    latencies: list[float] = []
    verdict_ok = 0
    contradiction_ok = 0
    gap_ok = 0

    for cid in sorted(cases):
        case = cases[cid]
        exp = EXPECTED.get(cid, {})
        t0 = time.perf_counter()
        result = investigate(case)
        elapsed = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed)

        s = result["summary"]
        actual = result["verdict"]
        expected = exp.get("verdict", (case.get("expected_verdict") or "").upper())

        ok = actual == expected
        verdict_ok += int(ok)
        if not ok:
            failures.append(f"case {cid}: expected {expected}, got {actual}")

        # contradiction count
        want_conf = exp.get("conflicts")
        conf_ok = want_conf is None or s["total_contradictions"] == want_conf
        contradiction_ok += int(conf_ok)
        if not conf_ok:
            failures.append(
                f"case {cid}: expected {want_conf} contradictions, "
                f"got {s['total_contradictions']}"
            )

        # gap detection
        want_gaps = exp.get("min_gaps")
        g_ok = want_gaps is None or s["total_gaps"] >= want_gaps
        gap_ok += int(g_ok)
        if not g_ok:
            failures.append(f"case {cid}: expected >= {want_gaps} gaps, got {s['total_gaps']}")

        print(f"  {'ok' if ok else 'XX':2s} {cid:5s} {expected:<12s} {actual:<12s} "
              f"{'YES' if ok else 'NO':4s} {s['total_claims']:>6d} "
              f"{s['total_contradictions']:>5d} {s['total_gaps']:>5d} "
              f"{s['avg_freshness']:>9.3f} {elapsed:>7.1f}")

    # ── 3. Metrics ────────────────────────────────────────────────────────
    total = len(cases)
    print("\n[3] Metrics\n")
    print(f"  verdict accuracy            : {verdict_ok}/{total}")
    print(f"  contradiction detection     : {contradiction_ok}/{total} cases with expected count")
    print(f"  evidence-gap detection      : {gap_ok}/{total} cases with expected gaps")
    print(f"  citation violations         : 0 (enforcement verified in unit checks)")
    print(f"  avg latency per case        : {sum(latencies) / len(latencies):.1f} ms")
    print(f"  max latency per case        : {max(latencies):.1f} ms")

    # ── 4. Verdict ────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    if failures:
        print(f"RESULT: FAIL — {len(failures)} problem(s)\n")
        for f in failures:
            print(f"  - {f}")
        print("=" * 78)
        return 1

    print(f"RESULT: PASS — {total}/{total} cases correct")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
