"""Disk-backed cache for external API results.

Every external API tool (Tavily, Serper, Firecrawl) MUST check this
cache before making a network call — researching the same company
twice within the TTL must cost zero API credits (MASTER.md rule A2).

Cache entries are JSON files under `.cache/`, keyed by a hash of
(provider, query). TTL comes from `settings.cache_ttl_hours`.
"""

import hashlib
import json
import time
from typing import Any

from app.utils.logger import get_logger
from config import CACHE_DIR, settings

log = get_logger("cache")


def _key_path(provider: str, query: str):
    digest = hashlib.sha256(f"{provider}::{query.strip().lower()}".encode()).hexdigest()[:32]
    return CACHE_DIR / f"{provider}_{digest}.json"


def get(provider: str, query: str) -> Any | None:
    """Return the cached result for (provider, query), or None if missing/expired."""
    path = _key_path(provider, query)
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        path.unlink(missing_ok=True)
        return None

    age_hours = (time.time() - entry["cached_at"]) / 3600
    if age_hours > settings.cache_ttl_hours:
        path.unlink(missing_ok=True)
        return None

    log.info("cache HIT for %s: %r (age %.1fh)", provider, query, age_hours)
    return entry["data"]


def put(provider: str, query: str, data: Any) -> None:
    """Store a result for (provider, query)."""
    path = _key_path(provider, query)
    entry = {"provider": provider, "query": query, "cached_at": time.time(), "data": data}
    path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("cache STORE for %s: %r", provider, query)
