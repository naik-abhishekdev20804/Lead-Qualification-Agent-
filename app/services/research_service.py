"""Deterministic lead research — runs tools without an LLM call.

Used by the API `POST /api/leads/{id}/research` endpoint so the dashboard
can refresh research findings without burning Gemini tokens.

Live mode (MOCK_MODE=FALSE) uses Tavily multi-query search + Firecrawl scrape.
When CRM website is a placeholder (example.com), discovers the real URL via Tavily.
"""

from app.mcp_tools import _mock_research
from app.mcp_tools import _research_extract as extract
from app.mcp_tools.company_research_tool import company_research
from app.mcp_tools.crm_lookup_tool import crm_lookup
from app.mcp_tools.website_analysis_tool import website_analysis
from app.utils.logger import get_logger
from config import settings

log = get_logger("research_service")

RESEARCH_SUMMARY_KEYS = (
    "company_overview",
    "recent_news",
    "growth_signals",
    "tech_stack",
    "sources",
    "detailed_summary",
    "official_website",
)


def _clip(text: str, max_chars: int) -> str:
    clean = (text or "").strip()
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3].rstrip() + "..."


def _limit_research_summary(summary: dict) -> dict:
    """Keep research payload concise and card-friendly for UI consumption."""
    limited = {**summary}
    limited["company_overview"] = _clip(
        limited.get("company_overview", ""),
        settings.research_overview_max_chars,
    )
    limited["recent_news"] = _clip(
        limited.get("recent_news", ""),
        settings.research_news_max_chars,
    )
    limited["detailed_summary"] = _clip(
        limited.get("detailed_summary", ""),
        settings.research_detailed_summary_max_chars,
    )
    limited["growth_signals"] = list(limited.get("growth_signals") or [])[: settings.research_max_growth_signals]
    limited["tech_stack"] = list(limited.get("tech_stack") or [])[: settings.research_max_tech_stack]
    limited["sources"] = list(limited.get("sources") or [])[: settings.research_max_sources]
    return limited


def _merge_unique_str_lists(*lists: list[str]) -> list[str]:
    merged: list[str] = []
    for values in lists:
        for value in values or []:
            if value and value not in merged:
                merged.append(value)
    return merged


def _blend_mock_with_live_web(company_name: str, web: dict, warnings: list[str]) -> dict:
    """Blend mock baseline with live web output so empty fields still have fallback text."""
    mock = _mock_research.mock_company_research(company_name)
    if not mock:
        return web

    if web.get("status") != "success":
        warnings.append("Live web research failed; using mock fallback for missing fields.")
        return mock

    if web.get("provider") == "mock":
        return web

    return {
        **web,
        "company_overview": web.get("company_overview") or mock.get("company_overview") or "",
        "recent_news": web.get("recent_news") or mock.get("recent_news") or "",
        "growth_signals": _merge_unique_str_lists(
            mock.get("growth_signals") or [],
            web.get("growth_signals") or [],
        ),
        "tech_stack": _merge_unique_str_lists(
            mock.get("tech_stack") or [],
            web.get("tech_stack") or [],
        ),
        "sources": _merge_unique_str_lists(
            mock.get("sources") or [],
            web.get("sources") or [],
        ),
        "search_results": web.get("search_results") or mock.get("search_results") or [],
    }


def _resolve_website_url(crm_website: str, web: dict) -> tuple[str, str | None]:
    """Return URL to scrape and optional note when CRM URL was replaced."""
    discovered = web.get("official_website") or ""
    if extract.is_placeholder_url(crm_website):
        if discovered:
            return discovered, f"CRM placeholder URL replaced with discovered site: {discovered}"
        return "", "CRM has placeholder URL and no official site was discovered via search."
    return crm_website, None


def run_lead_research(lead_id: str) -> dict:
    """Run the full research pipeline for one lead (CRM + web + website).

    Args:
        lead_id: CRM lead ID (e.g. "L-001").

    Returns:
        dict with status, lead_id, lead record, research_summary, website,
        providers used, and any warnings.
    """
    crm = crm_lookup(lead_id)
    if crm["status"] != "success":
        return {"status": "not_found", "lead_id": lead_id, "message": f"Lead '{lead_id}' not in CRM."}

    lead = crm["leads"][0]
    warnings: list[str] = []
    providers: list[str] = []

    web = company_research(lead["company"], lead["industry"])
    web = _blend_mock_with_live_web(lead["company"], web, warnings)
    if web["status"] != "success":
        warnings.append(f"Web research: {web.get('message', web['status'])}")
    else:
        providers.append(web.get("provider", "web"))

    scrape_url, url_note = _resolve_website_url(lead.get("website", ""), web)
    if url_note:
        warnings.append(url_note)

    site: dict = {
        "status": "skipped",
        "url": scrape_url,
        "title": "",
        "description": "",
        "headings": [],
        "tech_hints": [],
    }
    if scrape_url:
        site = website_analysis(scrape_url)
        if site["status"] == "success":
            providers.append(site.get("provider", "website"))
        elif site["status"] not in ("skipped",):
            warnings.append(f"Website analysis: {site.get('message', site['status'])}")

    tech_stack = list(web.get("tech_stack") or [])
    for hint in site.get("tech_hints") or []:
        if hint not in tech_stack:
            tech_stack.append(hint)

    sources = list(web.get("sources") or [])
    for src in (site.get("url"), web.get("official_website")):
        if src and src not in sources:
            sources.append(src)

    growth_signals = list(web.get("growth_signals") or [])
    site_growth = extract.extract_growth_signals(
        site.get("raw_excerpt", ""),
        site.get("description", ""),
        site.get("page_summary", ""),
    )
    for signal in site_growth:
        if signal not in growth_signals:
            growth_signals.append(signal)

    overview = extract.build_company_overview(
        web.get("tavily_answer") or web.get("company_overview") or "",
        web.get("search_results") or [],
        site.get("description") or "",
    )
    if site.get("page_summary") and len(overview) < 200:
        overview = f"{overview} {site['page_summary']}".strip()[:2000]

    news = web.get("recent_news") or ""
    detailed = web.get("detailed_summary") or extract.build_detailed_summary(
        overview=overview,
        news=news,
        growth_signals=growth_signals,
        tech_stack=tech_stack,
        headings=site.get("headings") or [],
        website_excerpt=site.get("raw_excerpt") or site.get("page_summary") or "",
    )

    research_summary = {
        "company_overview": overview,
        "recent_news": news,
        "growth_signals": growth_signals,
        "tech_stack": tech_stack,
        "sources": sources,
        "detailed_summary": detailed,
        "official_website": web.get("official_website") or (scrape_url if scrape_url else ""),
    }
    research_summary = _limit_research_summary(research_summary)

    log.info("research complete for %s via %s", lead_id, providers)

    return {
        "status": "success",
        "lead_id": lead_id,
        "lead": lead,
        "research_summary": research_summary,
        "website": {
            "url": site.get("url") or scrape_url,
            "title": site.get("title", ""),
            "description": site.get("description", ""),
            "headings": site.get("headings", []),
            "excerpt": site.get("raw_excerpt", "")[:500],
        },
        "providers": providers,
        "warnings": warnings,
        "mock": all(p == "mock" for p in providers) if providers else False,
        "live": any(p in ("tavily", "serper", "firecrawl") for p in providers),
    }
