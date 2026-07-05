"""Website analysis via Firecrawl (or mock when MOCK_MODE=TRUE).

Live mode uses Firecrawl v4 scrape API, extracts tech hints from page content,
and enriches overview when CRM only has placeholder URLs.
"""

from app.mcp_tools import _mock_research
from app.mcp_tools import _research_extract as extract
from app.security import sanitize_website_payload
from app.utils import api_budget, cache
from app.utils.api_budget import BudgetExceededError
from app.utils.logger import get_logger
from app.utils.provider_errors import classify_provider_exception
from config import settings

log = get_logger("website_analysis")


def _document_to_dict(doc) -> dict:
    """Normalize Firecrawl Document (v4) or legacy dict response."""
    if isinstance(doc, dict):
        return doc
    if hasattr(doc, "model_dump"):
        return doc.model_dump()
    return {
        "markdown": getattr(doc, "markdown", "") or "",
        "metadata": getattr(doc, "metadata", {}) or {},
        "summary": getattr(doc, "summary", "") or "",
    }


def _scrape_live(url: str) -> dict:
    if not settings.firecrawl_api_key:
        return {"status": "error", "message": "FIRECRAWL_API_KEY not configured."}

    try:
        api_budget.consume("firecrawl")
    except BudgetExceededError as exc:
        return {"status": "budget_exceeded", "message": str(exc)}

    try:
        # Firecrawl v4 primary API
        from firecrawl import Firecrawl

        client = Firecrawl(api_key=settings.firecrawl_api_key)
        doc = client.scrape(url, formats=["markdown"], only_main_content=True, timeout=60000)
        data = _document_to_dict(doc)
    except Exception as exc_v4:
        log.warning("Firecrawl v4 scrape failed for %r: %s — trying legacy API", url, exc_v4)
        try:
            from firecrawl import FirecrawlApp

            app = FirecrawlApp(api_key=settings.firecrawl_api_key)
            page = app.scrape_url(url, params={"formats": ["markdown"]})
            data = page if isinstance(page, dict) else _document_to_dict(page)
        except Exception as exc_legacy:
            status, message = classify_provider_exception("Firecrawl", exc_legacy)
            if status == "budget_exceeded":
                log.warning("Firecrawl quota/rate limit exhausted for %r: %s", url, exc_legacy)
            else:
                log.warning("Firecrawl legacy scrape failed for %r: %s", url, exc_legacy)
            return {"status": status, "message": message}

    markdown = data.get("markdown") or ""
    metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    title = metadata.get("title", "") or metadata.get("ogTitle", "")
    description = (
        metadata.get("description", "")
        or metadata.get("ogDescription", "")
        or data.get("summary", "")
    )
    tech_hints = extract.extract_tech_stack(markdown, description, title)

    return sanitize_website_payload({
        "status": "success",
        "provider": "firecrawl",
        "url": url,
        "title": title,
        "description": description,
        "headings": _extract_headings(markdown),
        "tech_hints": tech_hints,
        "raw_excerpt": markdown[:3000],
        "page_summary": (data.get("summary") or "")[:1500],
    })


def _extract_headings(markdown: str) -> list[str]:
    headings = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            headings.append(stripped.lstrip("#").strip())
        if len(headings) >= 10:
            break
    return headings


def website_analysis(url: str) -> dict:
    """Scrape and analyze a company's website.

    Extracts page title, meta description, key headings, and technology
    hints from page content. Results are cached for 24 hours.

    Args:
        url: Full website URL (e.g. "https://example.com").

    Returns:
        dict with status, provider, title, description, headings,
        tech_hints, raw_excerpt, and page_summary.
    """
    url = url.strip()
    if not url:
        return {
            "status": "error",
            "provider": "none",
            "url": url,
            "message": "No website URL provided.",
            "title": "",
            "description": "",
            "headings": [],
            "tech_hints": [],
        }

    if not url.startswith("http"):
        url = f"https://{url}"

    cached = cache.get("website_analysis", url)
    if cached:
        provider = cached.get("provider")
        # In mock mode, ignore previously cached live scrape data.
        if settings.mock_mode and provider != "mock":
            cached = None
        # In live mode, ignore stale mock scrape data.
        elif not settings.mock_mode and provider == "mock":
            cached = None
        else:
            return cached

    if settings.mock_mode:
        mock = _mock_research.mock_website_analysis(url)
        if mock:
            sanitized_mock = sanitize_website_payload(mock)
            cache.put("website_analysis", url, sanitized_mock)
            return sanitized_mock
        return {
            "status": "not_found",
            "provider": "mock",
            "url": url,
            "message": f"No mock website data for '{url}'.",
            "title": "",
            "description": "",
            "headings": [],
            "tech_hints": [],
        }

    if extract.is_placeholder_url(url):
        return {
            "status": "skipped",
            "provider": "firecrawl",
            "url": url,
            "message": "Placeholder CRM URL — use discovered official_website from web research.",
            "title": "",
            "description": "",
            "headings": [],
            "tech_hints": [],
        }

    live = _scrape_live(url)
    if live["status"] == "success":
        cache.put("website_analysis", url, live)
        return live

    if live.get("status") == "budget_exceeded":
        return {
            "status": "budget_exceeded",
            "provider": "firecrawl",
            "url": url,
            "message": live.get("message", "Daily scrape budget exhausted."),
            "title": "",
            "description": "",
            "headings": [],
            "tech_hints": [],
        }

    return {
        "status": "error",
        "provider": "firecrawl",
        "url": url,
        "message": live.get("message", "Scrape failed."),
        "title": "",
        "description": "",
        "headings": [],
        "tech_hints": [],
    }
