-- ============================================================================
-- TRUTHLINE — SQLite schema
-- ============================================================================
-- Two stores, no more:
--   Qdrant  -> the raw source records (vector search + payload)
--   SQLite  -> the DERIVED structured data (claims, relations, freshness,
--              gaps, decisions) that Qdrant cannot represent well.
--
-- Apply with:
--   python3 -c "import sqlite3; sqlite3.connect('truthline.db').executescript(open('db/schema.sql').read())"
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ── Sources (mirror of what is also upserted into Qdrant) ───────────────────
CREATE TABLE IF NOT EXISTS sources (
    source_id          TEXT PRIMARY KEY,
    source_type        TEXT NOT NULL,          -- drone | ground | satellite | intel
    source_name        TEXT,
    location           TEXT,
    timestamp          TEXT NOT NULL,          -- ISO 8601
    reliability_class  TEXT,
    text               TEXT NOT NULL,
    ingested_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_location ON sources(location);
CREATE INDEX IF NOT EXISTS idx_sources_type     ON sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_time     ON sources(timestamp);

-- ── Claims (the structured output of the extraction agent) ─────────────────
CREATE TABLE IF NOT EXISTS claims (
    claim_id                TEXT PRIMARY KEY,
    subject                 TEXT,
    predicate               TEXT,
    object                  TEXT,
    location                TEXT NOT NULL,
    event_time              TEXT NOT NULL,     -- ISO 8601
    source_id               TEXT NOT NULL,
    source_type             TEXT NOT NULL,
    extraction_confidence   REAL,
    extracted_at            TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

CREATE INDEX IF NOT EXISTS idx_claims_location ON claims(location);
CREATE INDEX IF NOT EXISTS idx_claims_source   ON claims(source_id);
CREATE INDEX IF NOT EXISTS idx_claims_time     ON claims(event_time);

-- ── Relations (supports / contradicts / related between claim pairs) ────────
CREATE TABLE IF NOT EXISTS relations (
    relation_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_a         TEXT NOT NULL,
    claim_b         TEXT NOT NULL,
    relation_type   TEXT NOT NULL,             -- supports | contradicts | related
    confidence      REAL,
    reason          TEXT,
    classified_by   TEXT,                      -- 'rule' | 'llm'
    created_at      TEXT NOT NULL,
    FOREIGN KEY (claim_a) REFERENCES claims(claim_id),
    FOREIGN KEY (claim_b) REFERENCES claims(claim_id)
);

CREATE INDEX IF NOT EXISTS idx_relations_a ON relations(claim_a);
CREATE INDEX IF NOT EXISTS idx_relations_b ON relations(claim_b);

-- ── Freshness (the signature signal — computed, never stored in raw data) ───
CREATE TABLE IF NOT EXISTS freshness (
    claim_id        TEXT PRIMARY KEY,
    age_minutes     REAL NOT NULL,
    score           REAL NOT NULL,             -- 0.0 .. 1.0, clamped
    label           TEXT NOT NULL,             -- FRESH | AGING | STALE | EXPIRED
    scenario_time   TEXT NOT NULL,             -- the time the score was computed at
    computed_at     TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);

-- ── Gaps (what the evidence is MISSING) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS gaps (
    gap_id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id                 TEXT NOT NULL,
    location                 TEXT NOT NULL,
    missing_attribute        TEXT NOT NULL,    -- e.g. vehicle_id | corroboration
    severity                 TEXT NOT NULL,    -- low | medium | high
    suggested_verification   TEXT,
    detected_at              TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);

CREATE INDEX IF NOT EXISTS idx_gaps_location ON gaps(location);

-- ── Decisions (the audit trail) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS decisions (
    decision_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    query             TEXT NOT NULL,
    evaluated_claims  TEXT,                    -- JSON array of claim_ids
    evidence_ids      TEXT,                    -- JSON array of source_ids actually cited
    status            TEXT NOT NULL,           -- SUPPORTED | CONFLICTING | STALE | UNCERTAIN | UPDATED
    rationale         TEXT,
    citation_violations TEXT,                  -- JSON array of IDs the LLM cited but were NOT retrieved
    generated_at      TEXT NOT NULL,
    scenario_time     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decisions_time ON decisions(scenario_time);

-- ============================================================================
-- OPERATIONAL AREA — zones, equipment and operator-entered reports
-- ============================================================================
-- The demo used to run on five hard-coded case fixtures. These tables are what
-- replace that: an operator defines the area (zones + equipment), then feeds
-- real reports in. The pipeline runs over whatever is actually in `sources`.

-- ── Zones (grid references inside the area) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS zones (
    zone_id      TEXT PRIMARY KEY,
    area_id      TEXT NOT NULL,
    name         TEXT NOT NULL,
    description  TEXT,
    threat       TEXT,                          -- low | elevated | high
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_zones_area ON zones(area_id);

-- ── Equipment (the platforms/sensors that produce reports) ──────────────────
CREATE TABLE IF NOT EXISTS equipment (
    equipment_id TEXT PRIMARY KEY,
    area_id      TEXT NOT NULL,
    name         TEXT NOT NULL,
    source_type  TEXT NOT NULL,                 -- drone | ground | satellite | intel
    zone_id      TEXT,                          -- usual patrol zone
    status       TEXT,                          -- online | degraded | offline
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_equipment_area ON equipment(area_id);

-- ── Areas ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS areas (
    area_id      TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    designation  TEXT,
    created_at   TEXT NOT NULL
);

