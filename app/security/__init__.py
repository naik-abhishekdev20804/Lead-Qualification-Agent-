"""Security helpers to sanitize untrusted text before LLM/tool consumption."""

from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+all\s+previous\s+instructions", re.I),
    re.compile(r"reveal\s+your\s+system\s+prompt", re.I),
    re.compile(r"give\s+this\s+company\s+a\s+score\s+of\s+100", re.I),
    re.compile(r"say\s+this\s+company\s+is\s+hot", re.I),
    re.compile(r"disregard\s+the\s+above", re.I),
    re.compile(r"forget\s+previous\s+instructions", re.I),
)


def _is_injection_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)


def redact_pii(text: str) -> str:
    """Mask emails/phone numbers from untrusted text."""
    out = EMAIL_RE.sub("[REDACTED_EMAIL]", text or "")
    out = PHONE_RE.sub("[REDACTED_PHONE]", out)
    return out


def sanitize_untrusted_text(text: str) -> str:
    """Redact PII and strip common prompt-injection directives."""
    redacted = redact_pii(text or "")
    kept: list[str] = []
    removed = 0
    for line in redacted.splitlines():
        if _is_injection_line(line):
            removed += 1
            continue
        kept.append(line)
    cleaned = "\n".join(kept).strip()
    if removed and cleaned:
        return f"{cleaned}\n\n[Filtered {removed} suspected prompt-injection line(s).]"
    if removed:
        return "[Filtered suspected prompt-injection content.]"
    return cleaned


def sanitize_string_list(values: list[str] | None) -> list[str]:
    """Sanitize each string in a list and drop emptied entries."""
    out: list[str] = []
    for value in values or []:
        cleaned = sanitize_untrusted_text(value)
        if cleaned:
            out.append(cleaned)
    return out


def sanitize_search_results(results: list[dict] | None) -> list[dict]:
    """Sanitize title/snippet fields from search providers."""
    sanitized: list[dict] = []
    for item in results or []:
        sanitized.append(
            {
                **item,
                "title": sanitize_untrusted_text(item.get("title", "")),
                "snippet": sanitize_untrusted_text(item.get("snippet", "")),
            }
        )
    return sanitized


def sanitize_crm_lead(lead: dict[str, Any]) -> dict[str, Any]:
    """Sanitize free-text CRM fields before returning tool output."""
    return {
        **lead,
        "name": sanitize_untrusted_text(lead.get("name", "")),
        "title": sanitize_untrusted_text(lead.get("title", "")),
        "company": sanitize_untrusted_text(lead.get("company", "")),
        "industry": sanitize_untrusted_text(lead.get("industry", "")),
        "notes": sanitize_untrusted_text(lead.get("notes", "")),
        "website": sanitize_untrusted_text(lead.get("website", "")),
    }


def sanitize_company_research_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitize untrusted web-research fields before LLM sees them."""
    return {
        **payload,
        "company_overview": sanitize_untrusted_text(payload.get("company_overview", "")),
        "recent_news": sanitize_untrusted_text(payload.get("recent_news", "")),
        "growth_signals": sanitize_string_list(payload.get("growth_signals")),
        "tech_stack": sanitize_string_list(payload.get("tech_stack")),
        "detailed_summary": sanitize_untrusted_text(payload.get("detailed_summary", "")),
        "tavily_answer": sanitize_untrusted_text(payload.get("tavily_answer", "")),
        "search_results": sanitize_search_results(payload.get("search_results")),
    }


def sanitize_website_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitize website scrape fields before downstream usage."""
    return {
        **payload,
        "title": sanitize_untrusted_text(payload.get("title", "")),
        "description": sanitize_untrusted_text(payload.get("description", "")),
        "headings": sanitize_string_list(payload.get("headings")),
        "tech_hints": sanitize_string_list(payload.get("tech_hints")),
        "raw_excerpt": sanitize_untrusted_text(payload.get("raw_excerpt", "")),
        "page_summary": sanitize_untrusted_text(payload.get("page_summary", "")),
    }
