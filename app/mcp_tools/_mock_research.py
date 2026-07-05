"""Load canned research payloads when MOCK_MODE=TRUE."""

import json
from functools import lru_cache

from config import DATA_DIR

_MOCK_FILE = DATA_DIR / "mock_research.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(_MOCK_FILE.read_text(encoding="utf-8"))


def mock_company_research(company_name: str) -> dict | None:
    """Return mock company research dict, or None if unknown."""
    data = _load()["by_company"].get(company_name.strip())
    if not data:
        return None
    return {
        "status": "success",
        "provider": "mock",
        "query": company_name,
        "company_overview": data["company_overview"],
        "recent_news": data["recent_news"],
        "growth_signals": data["growth_signals"],
        "tech_stack": data["tech_stack"],
        "sources": data["sources"],
        "search_results": data.get("search_snippets", []),
    }


def mock_website_analysis(url: str) -> dict | None:
    """Return mock website scrape dict, or None if unknown."""
    normalized = url.strip().rstrip("/")
    data = _load()["by_website"].get(normalized)
    if not data:
        # Try without trailing path variations
        for key, val in _load()["by_website"].items():
            if normalized.startswith(key.rstrip("/")):
                data = val
                break
    if not data:
        return None
    return {
        "status": "success",
        "provider": "mock",
        "url": url,
        "title": data["title"],
        "description": data["description"],
        "headings": data["headings"],
        "tech_hints": data["tech_hints"],
    }
