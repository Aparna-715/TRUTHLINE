"""
TRUTHLINE — Claim Extraction agent
===========================================================================
The one agent that turns prose into STRUCTURED CLAIMS.

This is where the project stops being a text search and becomes an
evidence-integrity engine. A retrieved chunk is not a claim; a claim carries
subject, predicate, object, location, event_time and source_id.

LLM: 1 call per report. Everything else in the pipeline is code.

Degrades gracefully: if the key is missing or the call fails, a deterministic
regex extractor runs instead so the pipeline never dead-ends.
"""

from __future__ import annotations

import json
import re
from typing import Callable

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import LLM_MAX_RETRIES, LLM_MODEL, LLM_TEMPERATURE, LLM_TIMEOUT, PROMPTS_DIR, get_openrouter_key
from db.store import now

__all__ = ["extract_claims", "llm_available", "deterministic_extract"]

_GRID = re.compile(r"\b(?:grid|zone|sector)[\s-]*([A-Za-z]?\d+)\b", re.I)
_ISO_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?")
_COUNT = re.compile(r"\b(\d+)\s+(vehicles?|personnel|troops?|units?|craft)\b", re.I)
_NEGATION = re.compile(r"\bno\s+(activity|vehicles?|movement|personnel)\b", re.I)


def llm_available() -> bool:
    """True if an OpenRouter key can be found. Prints nothing secret."""
    return get_openrouter_key() is not None


def _load_prompt(name: str) -> str:
    """Load a prompt from disk. Prompts are versioned, never hard-coded."""
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"prompt file missing: {path}")
    return path.read_text(encoding="utf-8")


def _call_openrouter(messages: list[dict]) -> str:
    """One chat completion call. Raises on any failure."""
    import httpx

    from config import OPENROUTER_URL

    key = get_openrouter_key()
    if not key:
        raise RuntimeError("no OpenRouter API key available")

    response = httpx.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": LLM_TEMPERATURE,
        },
        timeout=LLM_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _parse_claims(raw: str) -> list[dict]:
    """Pull a JSON array out of an LLM response, tolerating prose and fences."""
    text = (raw or "").strip()
    if not text:
        return []

    # Strip markdown fences if the model added them
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()

    # Find the outermost JSON array
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        text = text[start:end + 1]

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []

    if isinstance(parsed, dict):
        parsed = parsed.get("claims", [])
    if not isinstance(parsed, list):
        return []

    out = []
    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue
        out.append({
            "subject": item.get("subject"),
            "predicate": item.get("predicate"),
            "object": item.get("object"),
            "location": item.get("location"),
            "event_time": item.get("event_time"),
            "source_id": item.get("source_id"),
            "confidence": item.get("confidence"),
            "raw": item.get("text") or item.get("claim"),
        })
    return out


def deterministic_extract(text: str, source_id: str | None = None) -> list[dict]:
    """Offline fallback. Regex-based, no LLM.

    Produces coarse claims so the pipeline still functions without a key. The
    output is marked `classified_by: 'rule'` so it is never mistaken for
    model-extracted data.
    """
    clean = (text or "").strip()
    if not clean:
        return []

    location = None
    m = _GRID.search(clean)
    if m:
        raw = m.group(1)
        location = f"Grid-{raw.upper()}" if raw.isdigit() else f"Grid-{raw}"

    ts = None
    m = _ISO_TS.search(clean)
    if m:
        ts = m.group(0).replace(" ", "T")
        if len(ts) == 16:
            ts += ":00"

    claims: list[dict] = []
    neg = _NEGATION.search(clean)
    if neg:
        claims.append({
            "subject": location or "unknown",
            "predicate": "has_activity",
            "object": "none",
            "location": location,
            "event_time": ts,
            "source_id": source_id,
            "confidence": 0.5,
            "raw": neg.group(0),
            "classified_by": "rule",
        })

    for m in _COUNT.finditer(clean):
        claims.append({
            "subject": location or "unknown",
            "predicate": "vehicle_count",
            "object": f"{m.group(1)} {m.group(2).lower()}",
            "location": location,
            "event_time": ts,
            "source_id": source_id,
            "confidence": 0.5,
            "raw": m.group(0),
            "classified_by": "rule",
        })

    if not claims and clean:
        claims.append({
            "subject": location or "unknown",
            "predicate": "reported",
            "object": clean[:120],
            "location": location,
            "event_time": ts,
            "source_id": source_id,
            "confidence": 0.3,
            "raw": clean[:120],
            "classified_by": "rule",
        })

    return claims


def extract_claims(
    text: str,
    source_id: str | None = None,
    source_type: str | None = None,
    source_name: str | None = None,
    llm: Callable[[str], str] | None = None,
) -> list[dict]:
    """Extract structured claims from one report.

    Args:
        text: the report body.
        source_id: id to stamp onto each claim.
        llm: optional callable(text) -> str, injected for testing. When omitted
            the real OpenRouter call is used if a key is available.

    Returns:
        List of claim dicts. Never raises — returns [] on total failure.
    """
    if not (text or "").strip():
        return []

    raw = None
    error = None

    if llm is not None:
        try:
            raw = llm(text)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
    elif llm_available():
        try:
            prompt = _load_prompt("extract.txt").format(text=text)
            raw = _call_openrouter([{"role": "user", "content": prompt}])
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

    claims = _parse_claims(raw) if raw else []

    if not claims:
        claims = deterministic_extract(text, source_id)
        if error:
            for c in claims:
                c["extraction_note"] = f"LLM unavailable ({error}); rule fallback used"

    for i, c in enumerate(claims):
        c.setdefault("source_id", source_id)
        c["source_type"] = source_type
        c["source_name"] = source_name
        c.setdefault("classified_by", "llm" if raw else "rule")
        c["claim_id"] = f"{source_id or 'SRC'}-C{i + 1:03d}"
        c["extracted_at"] = now()

    return claims


if __name__ == "__main__":
    sample = (
        "Drone-Alpha at Grid-7 reports 3 vehicles detected at 2026-09-18T14:55:00. "
        "Ground-Beta at Grid-7 confirms 3 vehicles detected at 2026-09-18T14:57:00."
    )
    print("=== Claim Extraction agent ===\n")
    print(f"  LLM key available: {llm_available()}\n")
    for c in extract_claims(sample, source_id="DEMO-1", source_type="drone"):
        print(f"  {c['claim_id']}  {c['subject']} | {c['predicate']} | {c['object']}")
        print(f"      loc={c['location']} time={c['event_time']} by={c['classified_by']}")
