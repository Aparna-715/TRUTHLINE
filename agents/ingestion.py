"""
TRUTHLINE — Ingestion agent
===========================================================================
Raw text -> normalised source record -> SQLite + Qdrant.

NO LLM CALL. This agent is deterministic: cleaning text, detecting the source
type and location, and writing to both stores.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import TAU
from db.store import connect, init_db, insert_source, now
from retrieval.client import get_store

__all__ = ["ingest", "ingest_many", "detect_source_type", "detect_location", "normalise_text"]

# Order matters: check the most specific patterns first.
_SOURCE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("drone", re.compile(r"\bdrone\b|\buav\b", re.I)),
    ("satellite", re.compile(r"\bsatellite\b|\bsat-\d|\bimagery\b", re.I)),
    ("ground", re.compile(r"\bground\b|\bpatrol\b|\btroops?\b|\bunit\b", re.I)),
    ("intel", re.compile(r"\bintel\b|\bsigint\b|\bintercept\b|\bhumint\b", re.I)),
]

_ISO_TS = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?"
)
_GRID = re.compile(r"\b(?:grid|zone|sector|coord(?:inates)?)[\s-]*([A-Za-z]?\d+)\b", re.I)


def normalise_text(text: str) -> str:
    """Collapse whitespace and strip control characters. Nothing clever."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_source_type(text: str, source_name: str | None = None) -> str:
    """Infer the source type from the text or the source name."""
    for candidate in (source_name or "", text or ""):
        if not candidate:
            continue
        for stype, pattern in _SOURCE_PATTERNS:
            if pattern.search(candidate):
                return stype
    return "intel"  # unknown provenance: treat as lowest-urgency, longest tau


def detect_location(text: str) -> str | None:
    match = _GRID.search(text or "")
    if not match:
        return None
    raw = match.group(1)
    return f"Grid-{raw.upper()}" if raw.isdigit() else f"Grid-{raw}"


def detect_timestamp(text: str) -> str | None:
    match = _ISO_TS.search(text or "")
    if not match:
        return None
    raw = match.group(0).replace(" ", "T")
    if len(raw) == 16:  # no seconds
        raw += ":00"
    return raw


def ingest(
    text: str,
    source_id: str | None = None,
    source_type: str | None = None,
    location: str | None = None,
    timestamp: str | None = None,
    source_name: str | None = None,
    reliability_class: str | None = None,
    persist: bool = True,
) -> dict:
    """Turn one raw report into a stored source record.

    Args:
        text: the raw report body. Required.
        source_id: stable id. Generated if omitted.
        source_type: drone|ground|satellite|intel. Detected if omitted.
        location: grid name. Detected if omitted.
        timestamp: ISO 8601. Detected if omitted, else now.
        persist: write to SQLite + Qdrant. Set False to only build the record.

    Returns:
        The source record dict (also carrying `stored_sqlite` / `stored_qdrant`).
    """
    clean = normalise_text(text)
    if not clean:
        raise ValueError("ingest() received empty text")

    if source_id is None:
        digest = abs(hash(clean)) % 1_000_000
        source_id = f"SRC-{digest:06d}"

    record = {
        "source_id": source_id,
        "source_type": (source_type or detect_source_type(clean, source_name)).lower(),
        "source_name": source_name,
        "location": location or detect_location(clean),
        "timestamp": timestamp or detect_timestamp(clean) or now(),
        "reliability_class": reliability_class or "unrated",
        "text": clean,
        "ingested_at": now(),
    }

    if record["source_type"] not in TAU:
        record["source_type"] = detect_source_type(clean, source_name)

    record["stored_sqlite"] = False
    record["stored_qdrant"] = False

    if persist:
        try:
            conn = connect()
            init_db()
            insert_source(conn, record)
            record["stored_sqlite"] = True
        except Exception:
            record["stored_sqlite"] = False

        try:
            store = get_store()
            record["stored_qdrant"] = store.upsert([record]) > 0
        except Exception:
            record["stored_qdrant"] = False

    return record


def ingest_many(texts: Iterable[str], **kwargs) -> list[dict]:
    """Ingest a batch of reports."""
    return [ingest(t, **kwargs) for t in texts]


if __name__ == "__main__":
    sample = (
        "Drone-Alpha at Grid-7 reports 3 vehicles detected at 2026-09-18T14:55:00. "
        "Movement appears northward."
    )
    rec = ingest(sample, source_id="DEMO-1", persist=False)
    print("=== Ingestion agent ===\n")
    for k, v in rec.items():
        shown = v if k != "text" else f"{v[:60]}..."
        print(f"  {k:<18s} {shown}")
