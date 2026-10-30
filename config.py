"""
TRUTHLINE — Configuration
Central place for every tunable value. Nothing here is hard-coded elsewhere.

Import this everywhere instead of copying numbers into agent files:

    from config import TAU, STALE_THRESHOLD, QDRANT_URL

Keeping every constant in one file is what lets the team change a threshold
during a demo without hunting through six modules.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DB_DIR = PROJECT_ROOT / "db"
DB_PATH = PROJECT_ROOT / "truthline.db"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

# ── Knowledge decay (the signature feature) ───────────────────────────
# freshness = e^(-age / tau)   age and tau are both in MINUTES
TAU = {
    "drone": 5,        # fast-moving, goes stale almost immediately
    "ground": 15,      # slightly slower
    "satellite": 30,   # takes time to capture and downlink
    "intel": 1440,     # documents stay relevant for 24 hours
}
DEFAULT_TAU = 30

# Freshness label bands
BAND_FRESH = 0.7
BAND_AGING = 0.3
STALE_THRESHOLD = 0.1   # below this = stale / unusable

# ── Scenario clock ─────────────────────────────────────────────────────
# The operation's "now". Every freshness score is measured against this.
# Advancing it is the knowledge-decay demo — see the sidebar slider.
# This is deliberately NOT "the newest report": a case full of old reports must
# still be scored against the real clock, or stale evidence would look fresh.
SCENARIO_TIME = os.environ.get("TRUTHLINE_SCENARIO_TIME", "2026-09-18T15:00:00")

# ── Retrieval ─────────────────────────────────────────────────────────
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "truthline_sources"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
TOP_K = 10

# ── Contradiction candidate filter ────────────────────────────────────
# Two claims only become an LLM candidate pair if they share a location
# AND their event times are within this many minutes of each other.
# This filter is what keeps LLM cost and latency bounded.
CONTRADICTION_TIME_WINDOW_MIN = 60

# ── Corroboration ─────────────────────────────────────────────────────
MIN_SOURCES_FOR_CORROBORATION = 2

# ── LLM (OpenRouter) ──────────────────────────────────────────────────
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_MODEL = os.environ.get("TRUTHLINE_LLM_MODEL", "openai/gpt-4o-mini")
LLM_TEMPERATURE = 0.0
LLM_TIMEOUT = 60
LLM_MAX_RETRIES = 2

# Where the key lives on this machine. Never commit it.
_LOCAL_KEY_FILES = (
    Path("/home/weirdvella/Intern_15_PJT/AAAAAapi.txt"),
    PROJECT_ROOT / ".env",
)


# ── Feature gating (demo mode) ───────────────────────────────────────
# TRUTHLINE_DEMO_MODE=1 disables advanced/optional features so a demo can
# showcase only the solid core pipeline. Individual flags can still be
# overridden via TRUTHLINE_FEATURE_<NAME>=1/0.
import os as _os
_DEMO = _os.environ.get("TRUTHLINE_DEMO_MODE", "").strip().lower() in ("1", "true", "yes")

_DEFAULT_FEATURES = {
    "llm_contradiction": not _DEMO,   # LLM-upgraded contradiction classification
    "llm_rationale": not _DEMO,       # LLM prose for the Judge verdict
    "qdrant_retrieval": not _DEMO,    # semantic retrieval over Qdrant
    "advanced_console": not _DEMO,    # extra console widgets/panels
}

def feature_enabled(name: str) -> bool:
    """Return whether a named feature is enabled (env override wins)."""
    env_key = "TRUTHLINE_FEATURE_" + name.upper()
    raw = _os.environ.get(env_key)
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes")
    return _DEFAULT_FEATURES.get(name, True)


def get_openrouter_key() -> str | None:
    """Return the OpenRouter API key, or None if it cannot be found.

    Order: environment variable first, then known local key files.
    The key is never printed or logged.
    """
    env = os.environ.get("OPENROUTER_API_KEY")
    if env:
        return env.strip()

    for path in _LOCAL_KEY_FILES:
        try:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                name, value = line.split("=", 1)
                if "OPENROUTER" in name.upper() or "OPENAI" in name.upper():
                    return value.strip().strip('"').strip("'")
            elif line.startswith("sk-"):
                return line
    return None


def have_openrouter_key() -> bool:
    """True if a key is available. Safe to log — prints no secret."""
    return get_openrouter_key() is not None


# ── Quick self-check ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("TRUTHLINE configuration")
    print(f"  project root : {PROJECT_ROOT}")
    print(f"  database     : {DB_PATH}")
    print(f"  data dir     : {DATA_DIR}")
    print(f"  qdrant       : {QDRANT_URL}  collection={QDRANT_COLLECTION}")
    print(f"  llm          : {LLM_MODEL}")
    print(f"  tau          : {TAU}")
    print(f"  stale below  : {STALE_THRESHOLD}")
    print(f"  api key found: {have_openrouter_key()}")
