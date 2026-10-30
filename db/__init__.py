"""TRUTHLINE db package — SQLite access for the derived structured data."""
from .store import connect, init_db, insert_source, insert_claim, insert_relation, insert_freshness, insert_gap, insert_decision, fetch_all

__all__ = [
    "connect", "init_db",
    "insert_source", "insert_claim", "insert_relation",
    "insert_freshness", "insert_gap", "insert_decision",
    "fetch_all",
]
