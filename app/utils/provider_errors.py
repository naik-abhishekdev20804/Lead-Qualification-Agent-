"""Normalize provider API errors into stable tool statuses."""

from typing import Final

_EXHAUSTED_HINTS: Final[tuple[str, ...]] = (
    "429",
    "rate limit",
    "too many requests",
    "quota",
    "exhausted",
    "credits",
    "billing",
    "insufficient",
)


def _is_exhausted_error(message: str) -> bool:
    text = message.lower()
    return any(hint in text for hint in _EXHAUSTED_HINTS)


def classify_provider_exception(provider: str, exc: Exception) -> tuple[str, str]:
    """Map raw provider exceptions to (`status`, `message`) for tool responses."""
    raw_message = str(exc).strip() or f"{provider} request failed."
    if _is_exhausted_error(raw_message):
        return (
            "budget_exceeded",
            f"{provider} API quota/rate limit appears exhausted. "
            "Try again later or increase provider credits.",
        )
    return ("error", raw_message)

