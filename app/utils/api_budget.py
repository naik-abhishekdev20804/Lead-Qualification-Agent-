"""Daily API budget guard — the hard stop that keeps free tiers alive.

Each provider (tavily / serper / firecrawl / gemini) gets a daily call
counter persisted to `.cache/api_budget.json`. When a provider hits
`settings.daily_api_budget`, `BudgetExceededError` is raised and the
calling tool must degrade gracefully (return cached/mock data), never
crash the agent run (MASTER.md rule A3).

Usage inside a tool:
    from app.utils.api_budget import consume, BudgetExceededError

    try:
        consume("tavily")
    except BudgetExceededError:
        return {"status": "budget_exceeded", "results": []}
    ... make the real API call ...
"""

import json
from datetime import date

from app.utils.logger import get_logger
from config import CACHE_DIR, settings

log = get_logger("api_budget")

_BUDGET_FILE = CACHE_DIR / "api_budget.json"


class BudgetExceededError(Exception):
    """Raised when a provider's daily API budget is exhausted."""


def _load() -> dict:
    if _BUDGET_FILE.exists():
        try:
            state = json.loads(_BUDGET_FILE.read_text(encoding="utf-8"))
            if state.get("date") == date.today().isoformat():
                return state
        except (json.JSONDecodeError, OSError):
            pass
    return {"date": date.today().isoformat(), "counts": {}}


def _save(state: dict) -> None:
    _BUDGET_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def remaining(provider: str) -> int:
    """How many calls the provider has left today."""
    state = _load()
    used = state["counts"].get(provider, 0)
    return max(0, settings.daily_api_budget - used)


def consume(provider: str, amount: int = 1) -> None:
    """Record `amount` API calls for a provider. Raises if budget exhausted."""
    state = _load()
    used = state["counts"].get(provider, 0)
    if used + amount > settings.daily_api_budget:
        log.warning("BUDGET EXCEEDED for %s (%d/%d used today)", provider, used, settings.daily_api_budget)
        raise BudgetExceededError(
            f"Daily budget of {settings.daily_api_budget} calls exhausted for '{provider}'."
        )
    state["counts"][provider] = used + amount
    _save(state)
    log.info("api call: %s (%d/%d used today)", provider, used + amount, settings.daily_api_budget)


def usage_report() -> dict:
    """Current usage per provider — used by the report agent and dashboard."""
    state = _load()
    return {
        "date": state["date"],
        "budget_per_provider": settings.daily_api_budget,
        "used": state["counts"],
        "remaining": {p: settings.daily_api_budget - c for p, c in state["counts"].items()},
    }
