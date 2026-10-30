# TRUTHLINE — Evidence Integrity Engine

A fact-checker for intelligence reports. Reads reports from drones, satellites,
ground teams and radio logs that disagree, are hours old, or lack corroboration,
and returns an auditable verdict: **supported / conflicting / stale / uncertain /
updated**.

> **Not a chatbot.** TRUTHLINE never guesses. It extract claims, compare them,
> decay them by age, flag missing evidence, and judge only against retrieved
> sources. The UI shows what the pipeline already computed.

---

## Quick start

```bash
cd /home/weirdvella/Hkthn_30Oct/Truthline

# 1. Backend (FastAPI)
uvicorn api.main:app --reload --port 8000

# 2. Frontend (React + Vite)
cd frontend-react && npm run dev
# open http://localhost:5173
```

Verify:

```bash
python3 tests/run_all.py       # must print: RESULT: PASS — 5/5 cases correct
curl -s http://localhost:6333/collections   # Qdrant: {"status":"ok"...}
```

---

## Environment prerequisites

Two inputs drive the full LLM path. Both are optional — the code degrades
gracefully and works fully without either.

### 1. OpenRouter API key

Loaded by `config.py` (`get_openrouter_key()`), in order:

1. Env var `OPENROUTER_API_KEY`
2. `OPENROUTER_API_KEY=***` line in `/home/weirdvella/Intern_15_PJT/AAAAAapi.txt`
3. `OPENROUTER_API_KEY=***` line in `Truthline/.env`
4. A bare `sk-or-...` line (no `=`) in either file

Then:

```bash
python3 config.py | grep "api key found"   # must print: api key found: True
```

Workspace config is all in `config.py` (no separate `.env` required):

| Env var | Default | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | (none) | Your OpenRouter key |
| `TRUTHLINE_LLM_MODEL` | `openai/gpt-4o-mini` | Model for extraction / compare / judge |
| `TRUTHLINE_SCENARIO_TIME` | `2026-09-18T15:00:00` | The operation's "now" (decay clock) |
| `QDRANT_URL` | `http://localhost:6333` | Vector store address |

### 2. Qdrant (vector store)

```bash
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 -v ~/qdrant_storage:/qdrant/storage qdrant/qdrant
```

The `truthline_sources` collection is created on first connect. Retrieval and
timeline degrade gracefully (empty result + a warning) when it is down, so the
demo still runs.

---

## How to use

- **`/`** — Console. Provision an operational area (zones + equipment), feed
  real field reports, advance the scenario clock to decay your own evidence.
- **`/analysis`** — Full pipeline readout over the operator's own stored reports.
- **`/validation`** — The 5 labelled fixtures (proof, not demo).
- **`/case/:id`** — Drill-down on one fixture.

Demo moment: run Case E (`/case/E` or console analysis) and advance the scenario
clock — the verdict flips `UPDATED` → `STALE` as evidence decays.

---

## Architecture

```
Truthline/
├── agents/          Six pipeline modules (one job each), called in order:
│                     ingestion → claim_extract → contradiction → decay →
│                     evidence_gap → judge. Orchestrated in pipeline.py.
├── api/             FastAPI (11 routes + operational-area routes).
├── retrieval/       Qdrant client + embedders (graceful fallback).
├── graph/           Evidence graph (NetworkX + matplotlib).
├── models/          Pydantic schemas.
├── db/              SQLite schema + store (6 tables).
├── data/            case fixtures + generator + northstar corpus.
├── prompts/         LLM prompts (extract.txt, compare.txt, judge.txt).
├── tests/           Evaluation harness (the build gate).
├── frontend-react/  React 18 + Vite (Console / Analysis / Validation).
├── config.py        All tunable values + API-key loader.
└── truthline.db     SQLite runtime store (regenerated on start).
```

### The 6 agents

| # | Agent | File | LLM? |
|---|---|---|---|
| 1 | Ingestion | `agents/ingestion.py` | No |
| 2 | Claim extraction | `agents/claim_extraction.py` | Yes (1 call/report) |
| 3 | Contradiction | `agents/contradiction.py` | Yes (filtered pairs only) |
| 4 | Decay | `agents/decay.py` | No (pure maths) |
| 5 | Evidence gap | `agents/evidence_gap.py` | No |
| 6 | Judge | `agents/judge.py` | Yes (constrained, never trusted) |

### The verdict priority (Judge, first match wins)

1. `STALE` — every claim decayed (re-collect, don't adjudicate)
2. `UPDATED` — contradiction between stale claims + a fresh claim at same place
3. `CONFLICTING` — active contradiction between credible claims
4. `UNCERTAIN` — too few sources, or gaps exist
5. `SUPPORTED` — multiple independent fresh sources agree

---

## Data contract

Each source report: `id, source, source_type, location, event, timestamp`.
Each claim: `claim_id, subject, predicate, object, location, event_time,
source_id, source_type, extraction_confidence, freshness_score, freshness_label`.

`freshness_score` is **computed at runtime** (`exp(-age/tau)`), never stored in
data files. `location` is always `Grid-N`; `source_type` is `drone | ground |
satellite | intel`.

---

## Test gate

```bash
python3 tests/run_all.py
# RESULT: PASS — 5/5 cases correct   (exit=0)
```

All five cases pass including Case E (`UPDATED`): a fresh report overriding
stale ones. Metrics printed: verdict accuracy, contradiction detection, gap
detection, citation coverage, latency.

---

## Running from scratch (fresh machine)

```bash
cd /home/weirdvella/Hkthn_30Oct/Truthline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Qdrant (optional; retrieval degrades without it)
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 -v ~/qdrant_storage:/qdrant/storage qdrant/qdrant

# OpenRouter key (optional; falls back to deterministic rules)
export OPENROUTER_API_KEY="sk-or-..."
# or add OPENROUTER_API_KEY=*** to /home/weirdvella/Intern_15_PJT/AAAAAapi.txt

python3 tests/run_all.py
```

---

## Status

- Backend: `api/main.py` — 11 routes + operational area (zones/equipment/reports)
- Frontend: React 18 + Vite, clean production build, dark cyber-matrix theme
- Test gate: **5/5 green**
- Qdrant: running (optional — retrieval degrades gracefully)
- OpenRouter: optional (deterministic `rule`-fallback when absent)

## Resume

Say **TRUTHLINE-READY** in a chat to pick up exactly here.
