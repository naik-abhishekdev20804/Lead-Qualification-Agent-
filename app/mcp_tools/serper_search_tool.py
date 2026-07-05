"""Serper Google search — internal fallback for company_research_tool.

Not exposed directly to agents (MASTER.md A4: Tavily → Serper → cached/mock).
"""

import httpx

from app.utils import api_budget
from app.utils.api_budget import BudgetExceededError
from app.utils.logger import get_logger
from app.utils.provider_errors import classify_provider_exception
from config import settings

log = get_logger("serper")
_SERPER_URL = "https://google.serper.dev/search"


def _search_live(query: str, num_results: int) -> dict:
    if not settings.serper_api_key:
        return {"status": "error", "message": "SERPER_API_KEY not configured.", "results": []}

    try:
        api_budget.consume("serper")
    except BudgetExceededError as exc:
        return {"status": "budget_exceeded", "message": str(exc), "results": []}

    try:
        response = httpx.post(
            _SERPER_URL,
            headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num_results},
            timeout=20.0,
        )
        response.raise_for_status()
        organic = response.json().get("organic", [])
        results = [
            {"title": r.get("title", ""), "url": r.get("link", ""), "snippet": r.get("snippet", "")}
            for r in organic[:num_results]
        ]
        return {"status": "success", "provider": "serper", "query": query, "results": results}
    except Exception as exc:
        status, message = classify_provider_exception("Serper", exc)
        if status == "budget_exceeded":
            log.warning("Serper quota/rate limit exhausted for %r: %s", query, exc)
        else:
            log.warning("Serper search failed for %r: %s", query, exc)
        return {"status": status, "message": message, "results": []}
