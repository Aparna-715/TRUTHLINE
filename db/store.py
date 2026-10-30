"""
TRUTHLINE — SQLite store
===========================================================================
Holds the DERIVED structured data that Qdrant cannot represent well:
claims, relations, freshness, gaps, decisions.

The raw source records live in BOTH places — Qdrant for vector search, SQLite
for relational queries. Two stores, no more.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import DB_DIR, DB_PATH

__all__ = [
    "connect", "init_db", "now",
    "insert_source", "insert_claim", "insert_relation",
    "insert_freshness", "insert_gap", "insert_decision",
    "insert_area", "insert_zone", "insert_equipment",
    "delete_source", "clear_sources", "delete_zone", "delete_equipment",
    "fetch_all",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    p = Path(path) if path else DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str | Path | None = None) -> sqlite3.Connection:
    """Create the schema if it does not exist. Idempotent."""
    conn = connect(path)
    schema = DB_DIR / "schema.sql"
    if schema.exists():
        conn.executescript(schema.read_text(encoding="utf-8"))
        conn.commit()
    return conn


def _many(conn: sqlite3.Connection, sql: str, rows: Iterable[dict], keys: list[str]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    conn.executemany(
        sql,
        [tuple(r.get(k) for k in keys) for r in rows],
    )
    conn.commit()
    return len(rows)


def insert_source(conn: sqlite3.Connection, rec: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO sources
             (source_id, source_type, source_name, location, timestamp,
              reliability_class, text, ingested_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rec["source_id"], rec.get("source_type"), rec.get("source_name"),
            rec.get("location"), rec.get("timestamp"), rec.get("reliability_class"),
            rec.get("text", ""), rec.get("ingested_at") or now(),
        ),
    )
    conn.commit()


def insert_claim(conn: sqlite3.Connection, rec: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO claims
             (claim_id, subject, predicate, object, location, event_time,
              source_id, source_type, extraction_confidence, extracted_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rec["claim_id"], rec.get("subject"), rec.get("predicate"), rec.get("object"),
            rec["location"], rec.get("event_time"), rec.get("source_id"),
            rec.get("source_type"), rec.get("extraction_confidence"),
            rec.get("extracted_at") or now(),
        ),
    )
    conn.commit()


def insert_relation(conn: sqlite3.Connection, rec: dict) -> None:
    conn.execute(
        """INSERT INTO relations
             (claim_a, claim_b, relation_type, confidence, reason, classified_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            rec["claim_a"], rec["claim_b"], rec["relation_type"],
            rec.get("confidence"), rec.get("reason"),
            rec.get("classified_by") or "rule", rec.get("created_at") or now(),
        ),
    )
    conn.commit()


def insert_freshness(conn: sqlite3.Connection, rec: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO freshness
             (claim_id, age_minutes, score, label, scenario_time, computed_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            rec["claim_id"], rec.get("age_minutes"), rec.get("score"),
            rec.get("label"), rec.get("scenario_time"), rec.get("computed_at") or now(),
        ),
    )
    conn.commit()


def insert_gap(conn: sqlite3.Connection, rec: dict) -> None:
    conn.execute(
        """INSERT INTO gaps
             (claim_id, location, missing_attribute, severity,
              suggested_verification, detected_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            rec["claim_id"], rec["location"], rec["missing_attribute"],
            rec.get("severity") or "medium", rec.get("suggested_verification"),
            rec.get("detected_at") or now(),
        ),
    )
    conn.commit()


def insert_decision(conn: sqlite3.Connection, rec: dict) -> int:
    cur = conn.execute(
        """INSERT INTO decisions
             (query, evaluated_claims, evidence_ids, status, rationale,
              citation_violations, generated_at, scenario_time)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rec["query"],
            json.dumps(rec.get("evaluated_claims", [])),
            json.dumps(rec.get("evidence_ids", [])),
            rec["status"], rec.get("rationale"),
            json.dumps(rec.get("citation_violations", [])),
            rec.get("generated_at") or now(),
            rec.get("scenario_time"),
        ),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def fetch_all(conn: sqlite3.Connection, table: str, where: str = "", params: tuple = ()) -> list[dict]:
    """Read a whole table (or a filtered slice) as dicts."""
    allowed = {
        "sources", "claims", "relations", "freshness", "gaps", "decisions",
        "areas", "zones", "equipment",
    }
    if table not in allowed:
        raise ValueError(f"refusing to query unknown table {table!r}")
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ═══════════════════════════════════════════════════════════════════════
# OPERATIONAL AREA — zones, equipment, operator-entered reports
# ═══════════════════════════════════════════════════════════════════════

def insert_area(conn: sqlite3.Connection, rec: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO areas (area_id, name, designation, created_at)
           VALUES (?, ?, ?, ?)""",
        (rec["area_id"], rec["name"], rec.get("designation"), rec.get("created_at") or now()),
    )
    conn.commit()


def insert_zone(conn: sqlite3.Connection, rec: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO zones
             (zone_id, area_id, name, description, threat, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            rec["zone_id"], rec["area_id"], rec["name"], rec.get("description"),
            rec.get("threat") or "low", rec.get("created_at") or now(),
        ),
    )
    conn.commit()


def insert_equipment(conn: sqlite3.Connection, rec: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO equipment
             (equipment_id, area_id, name, source_type, zone_id, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            rec["equipment_id"], rec["area_id"], rec["name"], rec["source_type"],
            rec.get("zone_id"), rec.get("status") or "online",
            rec.get("created_at") or now(),
        ),
    )
    conn.commit()


def delete_source(conn: sqlite3.Connection, source_id: str) -> int:
    """Remove one report. Returns rows deleted (0 when the id is unknown)."""
    cur = conn.execute("DELETE FROM sources WHERE source_id = ?", (source_id,))
    conn.commit()
    return cur.rowcount


def clear_sources(conn: sqlite3.Connection) -> int:
    """Wipe every operator-entered report. Returns rows deleted."""
    cur = conn.execute("DELETE FROM sources")
    conn.commit()
    return cur.rowcount


def delete_zone(conn: sqlite3.Connection, zone_id: str) -> int:
    cur = conn.execute("DELETE FROM zones WHERE zone_id = ?", (zone_id,))
    conn.commit()
    return cur.rowcount


def delete_equipment(conn: sqlite3.Connection, equipment_id: str) -> int:
    cur = conn.execute("DELETE FROM equipment WHERE equipment_id = ?", (equipment_id,))
    conn.commit()
    return cur.rowcount


if __name__ == "__main__":
    conn = init_db()
    print("SQLite initialised at", DB_PATH)
    for t in ("sources", "claims", "relations", "freshness", "gaps", "decisions"):
        cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
        print(f"  {t:<10s} {len(cols):>2d} columns: {', '.join(cols)}")
