"""
TRUTHLINE — FastAPI backend
===========================================================================
The HTTP surface the React UI calls. Each endpoint is thin: it validates
input, calls one agent, and returns JSON. All the logic lives in agents/.

Run:
    uvicorn api.main:app --reload --port 8000
    -> http://localhost:8000/docs
"""

from __future__ import annotations

import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from agents.claim_extraction import extract_claims, llm_available  # noqa: E402
from agents.contradiction import find_contradictions  # noqa: E402
from agents.decay import batch_decay, calculate_freshness, get_freshness_label  # noqa: E402
from agents.evidence_gap import check_gaps  # noqa: E402
from agents.ingestion import ingest  # noqa: E402
from agents.judge import judge  # noqa: E402
from agents.pipeline import investigate, load_all_cases  # noqa: E402
from config import STALE_THRESHOLD, TAU  # noqa: E402
from db.store import (  # noqa: E402
    clear_sources,
    connect,
    delete_equipment,
    delete_source,
    delete_zone,
    fetch_all,
    init_db,
    insert_area,
    insert_decision,
    insert_equipment,
    insert_source,
    insert_zone,
)
from retrieval.client import get_store  # noqa: E402

app = FastAPI(
    title="TRUTHLINE",
    description="Evidence Integrity Engine — source-linked claim extraction, "
                "contradiction detection, temporal knowledge decay and "
                "evidence-gap analysis in one auditable workflow.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _naive_now() -> str:
    """Local wall-clock ISO, no timezone — the format operator input uses.

    Operator-entered report times are naive local ("2026-10-24T23:36:52"), so the
    live-area clock must be naive local too. Using the UTC-aware `_now()` here
    makes every age negative (the clamp then pins freshness to 1.0 and the whole
    board looks brand new).
    """
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ═══════════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════

class IngestRequest(BaseModel):
    text: str = Field(..., min_length=1)
    source_id: str | None = None
    source_type: str | None = None
    location: str | None = None
    timestamp: str | None = None
    source_name: str | None = None
    persist: bool = True


class ExtractRequest(BaseModel):
    text: str = Field(..., min_length=1)
    source_id: str | None = None
    source_type: str | None = None
    source_name: str | None = None


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1)
    location: str | None = None
    source_type: str | None = None
    limit: int = Field(10, ge=1, le=100)


class CompareRequest(BaseModel):
    claims: list[dict] = Field(..., description="Report dicts to compare pairwise")


class FreshnessRequest(BaseModel):
    reports: list[dict]
    scenario_time: str | None = None


class GapsRequest(BaseModel):
    claims: list[dict]


class JudgeRequest(BaseModel):
    claims: list[dict]
    relations: list[dict] = Field(default_factory=list)
    gaps: list[dict] = Field(default_factory=list)
    scenario_time: str | None = None


class InvestigateRequest(BaseModel):
    case_id: str | None = None
    reports: list[dict] | None = None
    scenario_time: str | None = None


class CaseResponse(BaseModel):
    case_id: str
    name: str
    expected_verdict: str
    report_count: int


# ── Operational area (zones / equipment / operator reports) ────────────────

class ZoneRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    threat: str = Field("low", description="low | elevated | high")
    area_id: str = "NORTHSTAR-1"


class EquipmentRequest(BaseModel):
    name: str = Field(..., min_length=1)
    source_type: str = Field(..., description="drone | ground | satellite | intel")
    zone_id: str | None = None
    status: str = "online"
    area_id: str = "NORTHSTAR-1"


class ReportRequest(BaseModel):
    """One operator-entered field report."""

    text: str = Field(..., min_length=1)
    zone: str = Field(..., min_length=1, description="zone_id or zone name")
    equipment_id: str | None = None
    source_type: str | None = None
    source_name: str | None = None
    timestamp: str | None = None
    reliability_class: str | None = None


# ═══════════════════════════════════════════════════════════════════════
# META
# ═══════════════════════════════════════════════════════════════════════

@app.get("/")
def root() -> dict:
    return {
        "name": "TRUTHLINE",
        "description": "Evidence Integrity Engine",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/v1/health")
def health() -> dict:
    """Store status + verdict counts + overall freshness."""
    store = get_store()
    conn = connect()
    init_db()

    counts = {s.lower(): 0 for s in ("SUPPORTED", "CONFLICTING", "STALE", "UNCERTAIN", "UPDATED")}
    for row in fetch_all(conn, "decisions"):
        status = (row.get("status") or "").lower()
        if status in counts:
            counts[status] += 1

    fresh_rows = fetch_all(conn, "freshness")
    avg_freshness = (
        round(sum(r["score"] for r in fresh_rows) / len(fresh_rows), 4)
        if fresh_rows else 0.0
    )

    return {
        "status": "ok",
        "time": _now(),
        "qdrant": store.health(),
        "sqlite": {"path": str(conn.execute("PRAGMA database_list").fetchone()[2]),
                   "tables": ["sources", "claims", "relations", "freshness", "gaps", "decisions"]},
        "llm": {"available": llm_available(), "model": "openai/gpt-4o-mini"},
        "tau": TAU,
        "stale_threshold": STALE_THRESHOLD,
        "verdict_counts": counts,
        "avg_freshness": avg_freshness,
        "totals": {
            "sources": len(fetch_all(conn, "sources")),
            "claims": len(fetch_all(conn, "claims")),
            "relations": len(fetch_all(conn, "relations")),
            "gaps": len(fetch_all(conn, "gaps")),
            "decisions": len(fetch_all(conn, "decisions")),
        },
    }


@app.get("/api/v1/cases")
def list_cases() -> dict:
    cases = load_all_cases()
    return {
        "cases": [
            CaseResponse(
                case_id=c["case_id"], name=c["name"],
                expected_verdict=c["expected_verdict"],
                report_count=len(c.get("reports", [])),
            ).model_dump()
            for c in cases.values()
        ]
    }


# ═══════════════════════════════════════════════════════════════════════
# AGENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/ingest")
def api_ingest(req: IngestRequest) -> dict:
    """Agent 1 — raw text -> stored source record. No LLM."""
    try:
        rec = ingest(
            text=req.text,
            source_id=req.source_id,
            source_type=req.source_type,
            location=req.location,
            timestamp=req.timestamp,
            source_name=req.source_name,
            persist=req.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"source_id": rec["source_id"], "record": rec}


@app.post("/api/v1/extract")
def api_extract(req: ExtractRequest) -> dict:
    """Agent 2 — report text -> structured claims. 1 LLM call."""
    claims = extract_claims(
        text=req.text,
        source_id=req.source_id,
        source_type=req.source_type,
        source_name=req.source_name,
    )
    return {"claim_count": len(claims), "claims": claims}


@app.post("/api/v1/retrieve")
def api_retrieve(req: RetrieveRequest) -> dict:
    """Agent 3 — Qdrant vector search with payload filters. No LLM."""
    store = get_store()
    hits = store.search(
        query_text=req.query,
        location=req.location,
        source_type=req.source_type,
        limit=req.limit,
    )
    return {
        "available": store.available,
        "count": len(hits),
        "evidence": hits,
        "warning": None if store.available else f"Qdrant unavailable: {store.error}",
    }


@app.post("/api/v1/compare")
def api_compare(req: CompareRequest) -> dict:
    """Agent 4 — rule pre-filter, then LLM classification of candidate pairs."""
    relations = find_contradictions(req.claims)
    return {
        "pair_count": len(relations),
        "relations": relations,
        "contradictions": [r for r in relations if r["relation_type"] == "contradicts"],
    }


@app.post("/api/v1/freshness")
def api_freshness(req: FreshnessRequest) -> dict:
    """Agent 5 (decay) — exp(-age/tau) per claim. Pure maths."""
    clock = req.scenario_time or (
        max((r["timestamp"] for r in req.reports if r.get("timestamp")), default=_now())
    )
    enriched = batch_decay(req.reports, clock)
    return {
        "scenario_time": clock,
        "stale_threshold": STALE_THRESHOLD,
        "freshness": [
            {
                "claim_id": c["id"],
                "source_type": c["source_type"],
                "age_minutes": c["age_minutes"],
                "score": c["freshness_score"],
                "label": c["freshness_label"],
                "is_stale": c["is_stale"],
            }
            for c in enriched
        ],
    }


@app.post("/api/v1/gaps")
def api_gaps(req: GapsRequest) -> dict:
    """Agent 5 (gaps) — deterministic missing-evidence rules."""
    gaps = check_gaps(req.claims)
    return {"gap_count": len(gaps), "gaps": gaps}


@app.post("/api/v1/judge")
def api_judge(req: JudgeRequest) -> dict:
    """Agent 6 — combine signals into a verdict. Constrained, not trusted."""
    decision = judge(
        claims=req.claims,
        relations=req.relations,
        gaps=req.gaps,
        scenario_time=req.scenario_time,
    )

    conn = connect()
    init_db()
    try:
        insert_decision(conn, {
            "query": "api:/judge",
            "status": decision["status"],
            "rationale": decision["rationale"],
            "evaluated_claims": decision["evaluated_claim_ids"],
            "evidence_ids": decision["evidence_ids"],
            "citation_violations": decision["citation_violations"],
            "scenario_time": req.scenario_time,
            "generated_at": decision["generated_at"],
        })
    except Exception:
        pass

    return decision


# ═══════════════════════════════════════════════════════════════════════
# ORCHESTRATION
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/investigate")
def api_investigate(req: InvestigateRequest) -> dict:
    """Run the WHOLE pipeline over one case. This is the demo's main call."""
    if req.reports:
        case = {"case_id": "LIVE", "name": "Live analysis", "reports": req.reports}
    elif req.case_id:
        cases = load_all_cases()
        if req.case_id not in cases:
            raise HTTPException(status_code=404, detail=f"unknown case {req.case_id!r}")
        case = cases[req.case_id]
    else:
        raise HTTPException(status_code=400, detail="supply either case_id or reports")

    result = investigate(
        case,
        scenario_time=req.scenario_time,
        llm_classify=_make_llm_classify(),
        llm_rationale=_make_llm_rationale(),
    )

    conn = connect()
    init_db()
    try:
        insert_decision(conn, {
            "query": f"case:{case.get('case_id')}",
            "status": result["verdict"],
            "rationale": result["rationale"],
            "evaluated_claims": result["summary"] and [
                c["id"] for c in result["claims"]
            ] or [],
            "evidence_ids": result["evidence_ids"],
            "citation_violations": result["citation_violations"],
            "scenario_time": result["summary"].get("scenario_time"),
            "generated_at": result["generated_at"],
        })
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════════════
# VISUALISATION
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/v1/timeline")
def api_timeline(scenario_time: str | None = None, location: str | None = None) -> dict:
    """Events for the timeline plot, colour-coded by source type."""
    store = get_store()
    sources = store.all_sources(location=location)

    events = []
    for s in sources:
        events.append({
            "source_id": s.get("source_id"),
            "source_type": s.get("source_type"),
            "source_name": s.get("source_name"),
            "location": s.get("location"),
            "timestamp": s.get("timestamp"),
            "text": (s.get("text") or "")[:200],
        })

    events.sort(key=lambda e: e.get("timestamp") or "")
    return {
        "available": store.available,
        "scenario_time": scenario_time,
        "location": location,
        "count": len(events),
        "events": events,
        "warning": None if store.available else f"Qdrant unavailable: {store.error}",
    }


@app.get("/api/v1/graph")
def api_graph(claim_id: str | None = None) -> dict:
    """Nodes + edges for the evidence graph. Nodes are CLAIMS, not documents."""
    from graph.evidence_graph import build_graph

    conn = connect()
    init_db()
    claims = fetch_all(conn, "claims")
    relations = fetch_all(conn, "relations")

    if claim_id:
        related = {
            r["claim_a"] for r in relations if r["claim_b"] == claim_id
        } | {
            r["claim_b"] for r in relations if r["claim_a"] == claim_id
        }
        related.add(claim_id)
        claims = [c for c in claims if c["claim_id"] in related]
        relations = [
            r for r in relations
            if r["claim_a"] in related and r["claim_b"] in related
        ]

    return build_graph(claims, relations)


# ═══════════════════════════════════════════════════════════════════════
# OPERATIONAL AREA — zones, equipment, operator-entered reports
# ═══════════════════════════════════════════════════════════════════════
# This is what replaces the hard-coded case fixtures as the primary workflow.
# An operator provisions an area (zones + equipment), then feeds real reports
# in. /investigate runs over whatever is actually stored in `sources`.

def _slug(text: str) -> str:
    """Lowercase, hyphenated id from a human name. 'Grid-7' -> 'grid-7'."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")


def _source_to_report(row: dict) -> dict:
    """Map a SQLite `sources` row onto the report shape the pipeline expects.

    The pipeline (and the case fixtures) use {id, source, source_type,
    location, event, timestamp}. The sources table stores the same facts under
    {source_id, source_name, ..., text}. This is the one place that translation
    happens.
    """
    return {
        "id": row.get("source_id"),
        "source": row.get("source_name") or row.get("source_id"),
        "source_type": row.get("source_type") or "intel",
        "location": row.get("location") or "UNKNOWN",
        "event": row.get("text") or "",
        "timestamp": row.get("timestamp"),
        "reliability_class": row.get("reliability_class"),
    }


def _all_reports(conn) -> list[dict]:
    rows = fetch_all(conn, "sources")
    reports = [_source_to_report(r) for r in rows]
    reports.sort(key=lambda r: r.get("timestamp") or "")
    return reports


def _zone_summary(reports: list[dict], zones: list[dict], scenario_time: str | None) -> list[dict]:
    """Per-zone rollup: how many reports, how fresh, which sources."""
    clock = scenario_time or _naive_now()
    enriched = batch_decay(reports, clock) if reports else []

    by_loc: dict[str, list[dict]] = {}
    for c in enriched:
        by_loc.setdefault(c.get("location") or "UNKNOWN", []).append(c)

    # Zones the operator defined come first, even when they hold no reports.
    known = {z["name"]: z for z in zones}
    names = list(known.keys()) + [n for n in by_loc if n not in known]

    out = []
    for name in names:
        claims = by_loc.get(name, [])
        scores = [c["freshness_score"] for c in claims]
        out.append({
            "zone_id": known.get(name, {}).get("zone_id") or _slug(name),
            "name": name,
            "description": known.get(name, {}).get("description"),
            "threat": known.get(name, {}).get("threat") or "low",
            "report_count": len(claims),
            "source_count": len({c.get("source") for c in claims}),
            "stale_count": sum(1 for c in claims if c.get("is_stale")),
            "avg_freshness": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "sources": sorted({c.get("source_type") or "intel" for c in claims}),
        })
    return out


# ── LLM-backed optional callables (wired into /investigate) ────────────────

def _make_llm_classify():
    """Build a real LLM relation classifier (OpenRouter). Returns None if the
    API key is missing, in which case the pipeline falls back to rule-only."""
    from config import LLM_MODEL, OPENROUTER_URL, get_openrouter_key

    key = get_openrouter_key()
    if not key:
        return None

    import httpx
    from pathlib import Path

    _prompt = (
        Path(__file__).resolve().parent.parent / "prompts" / "compare.txt"
    ).read_text(encoding="utf-8")

    def classify(a: dict, b: dict) -> str:
        try:
            body = _prompt.format(
                source_a=a.get("source") or a.get("id"),
                event_a=a.get("event") or "",
                source_b=b.get("source") or b.get("id"),
                event_b=b.get("event") or "",
            )
            resp = httpx.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LLM_MODEL,
                    "messages": [{"role": "user", "content": body}],
                    "temperature": 0.0,
                },
                timeout=60,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            import json as _json
            parsed = _json.loads(content)
            kind = str(parsed.get("relation_type") or "").strip().lower()
            if kind not in {"supports", "contradicts", "related"}:
                kind = "related"
            return kind
        except Exception:
            return "related"  # degrade: never block the demo

    return classify


def _make_llm_rationale():
    """Build an LLM prose generator for the Judge. Returns None if the API key
    is missing, in which case the pipeline uses a deterministic rationale."""
    from config import LLM_MODEL, OPENROUTER_URL, get_openrouter_key

    key = get_openrouter_key()
    if not key:
        return None

    import httpx
    from pathlib import Path

    _prompt = (
        Path(__file__).resolve().parent.parent / "prompts" / "judge.txt"
    ).read_text(encoding="utf-8")

    def rationale(context: dict) -> str:
        try:
            body = _prompt.format(
                status=context.get("status", ""),
                evidence_ids=" ".join(str(i) for i in context.get("evidence_ids") or []),
                claims="\n".join(str(c) for c in context.get("claims") or []),
                conflicts="\n".join(str(c) for c in context.get("conflicts") or []),
                gaps="\n".join(str(g) for g in context.get("gaps") or []),
            )
            resp = httpx.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LLM_MODEL,
                    "messages": [{"role": "user", "content": body}],
                    "temperature": 0.0,
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    return rationale


@app.get("/api/v1/area")
def get_area(scenario_time: str | None = None) -> dict:
    """The whole operational picture: area, zones, equipment, reports."""
    conn = connect()
    init_db()

    areas = fetch_all(conn, "areas")
    zones = fetch_all(conn, "zones")
    equipment = fetch_all(conn, "equipment")
    reports = _all_reports(conn)

    return {
        "area": areas[0] if areas else None,
        "zones": _zone_summary(reports, zones, scenario_time),
        "equipment": equipment,
        "reports": reports,
        "report_count": len(reports),
        "zone_count": len(zones),
        "equipment_count": len(equipment),
    }


DEFAULT_AREA = {
    "area_id": "NORTHSTAR-1",
    "name": "Sector NORTHSTAR",
    "designation": "AO-7 · Defence / Aerospace",
}

DEFAULT_ZONES = [
    {"name": "Grid-7", "description": "Ridge crossing — primary vehicle corridor", "threat": "elevated"},
    {"name": "Grid-8", "description": "Supply route — unimproved road", "threat": "low"},
    {"name": "Grid-12", "description": "Valley basin — low visibility", "threat": "elevated"},
    {"name": "Ridge-3", "description": "High ground — observation post", "threat": "low"},
    {"name": "Valley-9", "description": "River fork — crossing point", "threat": "high"},
]

DEFAULT_EQUIPMENT = [
    {"name": "Drone-Alpha", "source_type": "drone", "zone_id": "grid-7", "status": "online"},
    {"name": "Drone-Bravo", "source_type": "drone", "zone_id": "grid-8", "status": "online"},
    {"name": "Ground-Sentry-1", "source_type": "ground", "zone_id": "grid-12", "status": "online"},
    {"name": "Satellite-Kestrel", "source_type": "satellite", "zone_id": "ridge-3", "status": "online"},
    {"name": "Intel-Feed-Delta", "source_type": "intel", "zone_id": "valley-9", "status": "degraded"},
]


@app.post("/api/v1/area/seed")
def seed_area() -> dict:
    """Provision the default area: zones + equipment roster. No fake reports.

    This gives you a realistic structure to hang real reports on. It never
    inserts sample observations — the evidence is always yours.
    """
    conn = connect()
    init_db()

    insert_area(conn, {**DEFAULT_AREA, "created_at": _now()})
    for z in DEFAULT_ZONES:
        insert_zone(conn, {
            "zone_id": _slug(z["name"]),
            "area_id": DEFAULT_AREA["area_id"],
            **z,
            "created_at": _now(),
        })
    for e in DEFAULT_EQUIPMENT:
        insert_equipment(conn, {
            "equipment_id": _slug(e["name"]),
            "area_id": DEFAULT_AREA["area_id"],
            **e,
            "created_at": _now(),
        })

    return {
        "area": DEFAULT_AREA,
        "zones_created": len(DEFAULT_ZONES),
        "equipment_created": len(DEFAULT_EQUIPMENT),
    }


@app.post("/api/v1/zones")
def create_zone(req: ZoneRequest) -> dict:
    conn = connect()
    init_db()
    zone_id = _slug(req.name)
    if not zone_id:
        raise HTTPException(status_code=400, detail="zone name produced an empty id")
    insert_zone(conn, {
        "zone_id": zone_id,
        "area_id": req.area_id,
        "name": req.name,
        "description": req.description,
        "threat": req.threat,
        "created_at": _now(),
    })
    return {"zone_id": zone_id, "name": req.name}


@app.delete("/api/v1/zones/{zone_id}")
def remove_zone(zone_id: str) -> dict:
    conn = connect()
    init_db()
    deleted = delete_zone(conn, zone_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"unknown zone {zone_id!r}")
    return {"deleted": deleted, "zone_id": zone_id}


@app.post("/api/v1/equipment")
def create_equipment(req: EquipmentRequest) -> dict:
    if req.source_type.lower() not in TAU:
        raise HTTPException(
            status_code=400,
            detail=f"source_type must be one of {sorted(TAU)}, got {req.source_type!r}",
        )
    conn = connect()
    init_db()
    equipment_id = _slug(req.name)
    if not equipment_id:
        raise HTTPException(status_code=400, detail="equipment name produced an empty id")
    insert_equipment(conn, {
        "equipment_id": equipment_id,
        "area_id": req.area_id,
        "name": req.name,
        "source_type": req.source_type.lower(),
        "zone_id": req.zone_id,
        "status": req.status,
        "created_at": _now(),
    })
    return {"equipment_id": equipment_id, "name": req.name}


@app.delete("/api/v1/equipment/{equipment_id}")
def remove_equipment(equipment_id: str) -> dict:
    conn = connect()
    init_db()
    deleted = delete_equipment(conn, equipment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"unknown equipment {equipment_id!r}")
    return {"deleted": deleted, "equipment_id": equipment_id}


@app.get("/api/v1/reports")
def list_reports() -> dict:
    """Every operator-entered report, oldest first."""
    conn = connect()
    init_db()
    reports = _all_reports(conn)
    return {"count": len(reports), "reports": reports}


@app.post("/api/v1/reports")
def create_report(req: ReportRequest) -> dict:
    """Record one field report against a zone, from a named piece of equipment.

    Goes through the real ingestion agent so source type, timestamp and text
    normalisation behave exactly as they do for the fixture data.
    """
    conn = connect()
    init_db()

    source_type = req.source_type
    source_name = req.source_name

    # If the operator picked a piece of equipment, inherit its type and name.
    if req.equipment_id:
        for e in fetch_all(conn, "equipment"):
            if e["equipment_id"] == req.equipment_id:
                source_type = source_type or e["source_type"]
                source_name = source_name or e["name"]
                break

    source_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
    try:
        record = ingest(
            text=req.text,
            source_id=source_id,
            source_type=source_type,
            location=req.zone,
            timestamp=req.timestamp,
            source_name=source_name,
            reliability_class=req.reliability_class,
            persist=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"report": _source_to_report({
        "source_id": record["source_id"],
        "source_name": record.get("source_name"),
        "source_type": record.get("source_type"),
        "location": record.get("location"),
        "text": record.get("text"),
        "timestamp": record.get("timestamp"),
        "reliability_class": record.get("reliability_class"),
    })}


@app.delete("/api/v1/reports/{source_id}")
def remove_report(source_id: str) -> dict:
    conn = connect()
    init_db()
    deleted = delete_source(conn, source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"unknown report {source_id!r}")
    return {"deleted": deleted, "source_id": source_id}


@app.delete("/api/v1/reports")
def clear_all_reports() -> dict:
    """Wipe the board. Zones and equipment survive."""
    conn = connect()
    init_db()
    return {"deleted": clear_sources(conn)}


@app.post("/api/v1/area/investigate")
def investigate_area(scenario_time: str | None = None, zone: str | None = None) -> dict:
    """Run the full pipeline over the operator's OWN reports.

    Optionally scoped to a single zone. This is the real-data counterpart to
    /investigate, which runs the labelled fixtures.
    """
    conn = connect()
    init_db()
    reports = _all_reports(conn)

    if zone:
        reports = [r for r in reports if r.get("location") == zone]

    if not reports:
        return {
            "case_id": "AREA",
            "case_name": zone or "Operational area",
            "claims": [], "relations": [], "gaps": [], "freshness": [],
            "verdict": "UNCERTAIN",
            "rationale": (
                "No reports on the board. Add field reports from the equipment "
                "roster, then re-run the analysis."
            ),
            "evidence_ids": [],
            "citation_violations": [],
            "summary": {
                "total_claims": 0, "total_relations": 0, "total_contradictions": 0,
                "total_supports": 0, "total_gaps": 0, "stale_count": 0,
                "avg_freshness": 0.0, "locations_checked": 0,
                "scenario_time": scenario_time or _naive_now(),
            },
            "generated_at": _now(),
        }

    case = {
        "case_id": "AREA",
        "name": zone or "Operational area",
        "reports": reports,
    }
    # The live clock must default to NOW. Passing None lets the pipeline fall
    # back to config.SCENARIO_TIME — the fixture date (2026-09-18) — which makes
    # every real report look like it is 36 days in the future.
    return investigate(
        case,
        scenario_time=scenario_time or _naive_now(),
        llm_classify=_make_llm_classify(),
        llm_rationale=_make_llm_rationale(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
