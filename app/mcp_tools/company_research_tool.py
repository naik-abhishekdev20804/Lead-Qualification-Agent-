"""Company web research via Tavily (primary) with Serper fallback.

Live mode runs multiple targeted Tavily queries (overview + news) with
advanced search depth and synthesized answers for richer detail than CRM alone.
Every call: cache → mock (if MOCK_MODE) → live APIs. Never raises (MASTER.md C3).
"""

from app.mcp_tools import _mock_research
from app.mcp_tools import _research_extract as extract
from app.mcp_tools.serper_search_tool import _search_live as _serper_search
from app.security import sanitize_company_research_payload
from app.utils import api_budget, cache
from app.utils.api_budget import BudgetExceededError
from app.utils.logger import get_logger
from app.utils.provider_errors import classify_provider_exception
from config import settings

log = get_logger("company_research")

_OVERVIEW_QUERY = "{company} {industry} company overview products leadership employees"
_NEWS_QUERY = "{company} latest news funding hiring expansion 2025 2026"


def _search_tavily(
    query: str,
    max_results: int,
    search_depth: str,
    topic: str | None,
    include_answer: str | bool | None,
    time_range: str | None,
) -> dict:
    if not settings.tavily_api_key:
        return {"status": "error", "message": "TAVILY_API_KEY not configured.", "results": [], "answer": ""}

    try:
        api_budget.consume("tavily")
    except BudgetExceededError as exc:
        return {"status": "budget_exceeded", "message": str(exc), "results": [], "answer": ""}

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        kwargs: dict = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
        }
        if topic:
            kwargs["topic"] = topic
        if include_answer is not None:
            kwargs["include_answer"] = include_answer
        if time_range:
            kwargs["time_range"] = time_range

        response = client.search(**kwargs)
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in response.get("results", [])
        ]
        return {
            "status": "success",
            "provider": "tavily",
            "query": query,
            "results": results,
            "answer": response.get("answer") or "",
        }
    except Exception as exc:
        status, message = classify_provider_exception("Tavily", exc)
        if status == "budget_exceeded":
            log.warning("Tavily quota/rate limit exhausted for %r: %s", query, exc)
        else:
            log.warning("Tavily search failed for %r: %s", query, exc)
        return {"status": status, "message": message, "results": [], "answer": ""}


def _normalize_results(raw: dict) -> dict:
    """Turn provider-specific search output into the standard research shape."""
    results = raw.get("results") or raw.get("search_results") or []
    snippets = " ".join(r.get("snippet", "") for r in results[:3])
    sources = list({r.get("url", "") for r in results if r.get("url")})[:5]

    normalized = {
        "status": "success",
        "provider": raw.get("provider", "unknown"),
        "query": raw.get("query", ""),
        "company_overview": raw.get("company_overview") or snippets[:500] or "No overview found.",
        "recent_news": raw.get("recent_news") or (results[0]["snippet"] if results else "No recent news found."),
        "growth_signals": raw.get("growth_signals") or [],
        "tech_stack": raw.get("tech_stack") or [],
        "sources": raw.get("sources") or sources,
        "search_results": results,
        "official_website": raw.get("official_website"),
        "detailed_summary": raw.get("detailed_summary", ""),
        "tavily_answer": raw.get("tavily_answer", ""),
    }
    return sanitize_company_research_payload(normalized)


def _normalize_live(company_name: str, industry: str, overview_raw: dict, news_raw: dict) -> dict:
    """Build rich research fields from multi-query Tavily live results."""
    overview_results = overview_raw.get("results") or []
    news_results = news_raw.get("results") or []
    all_results = overview_results + news_results

    answer = " ".join(
        a for a in (overview_raw.get("answer", ""), news_raw.get("answer", "")) if a
    ).strip()

    overview = extract.build_company_overview(answer, overview_results, "")
    news = extract.build_recent_news(overview_results, news_results)
    growth = extract.extract_growth_signals(answer, overview, news)
    tech = extract.extract_tech_stack(answer, overview, news)
    sources = extract.collect_sources(overview_results, news_results)
    official = extract.discover_official_website(company_name, all_results)

    detailed = extract.build_detailed_summary(
        overview=overview,
        news=news,
        growth_signals=growth,
        tech_stack=tech,
        headings=[],
        website_excerpt="",
    )

    normalized = {
        "status": "success",
        "provider": "tavily",
        "query": overview_raw.get("query", ""),
        "company_overview": overview,
        "recent_news": news,
        "growth_signals": growth,
        "tech_stack": tech,
        "sources": sources,
        "search_results": all_results,
        "official_website": official,
        "detailed_summary": detailed,
        "tavily_answer": answer,
    }
    return sanitize_company_research_payload(normalized)


def _live_research(company_name: str, industry: str) -> dict:
    """Multi-query Tavily research for detailed live company intel."""
    overview_q = _OVERVIEW_QUERY.format(company=company_name, industry=industry)
    news_q = _NEWS_QUERY.format(company=company_name)

    overview = _search_tavily(
        overview_q,
        max_results=8,
        search_depth="advanced",
        topic=None,
        include_answer="advanced",
        time_range=None,
    )
    news = _search_tavily(
        news_q,
        max_results=6,
        search_depth="advanced",
        topic="news",
        include_answer="basic",
        time_range="year",
    )

    if overview.get("results") or news.get("results"):
        return _normalize_live(company_name, industry, overview, news)

    # Serper fallback — single combined query
    log.info(
        "Tavily unavailable/empty for %r (%s, %s) — trying Serper fallback",
        company_name,
        overview.get("status"),
        news.get("status"),
    )
    serper_q = f"{company_name} {industry} company overview news funding"
    serper = _serper_search(serper_q, num_results=8)
    if serper["status"] == "success" and serper.get("results"):
        results = serper["results"]
        overview_text = extract.build_company_overview("", results, "")
        news_text = extract.build_recent_news(results, results)
        return sanitize_company_research_payload({
            "status": "success",
            "provider": "serper",
            "query": serper_q,
            "company_overview": overview_text,
            "recent_news": news_text,
            "growth_signals": extract.extract_growth_signals(overview_text, news_text),
            "tech_stack": extract.extract_tech_stack(overview_text, news_text),
            "sources": extract.collect_sources(results),
            "search_results": results,
            "official_website": extract.discover_official_website(company_name, results),
            "detailed_summary": extract.build_detailed_summary(
                overview_text, news_text,
                extract.extract_growth_signals(overview_text, news_text),
                extract.extract_tech_stack(overview_text, news_text),
                [], "",
            ),
            "tavily_answer": "",
        })

    tavily_message = overview.get("message") or news.get("message") or "Tavily search failed."
    if (
        overview.get("status") == "budget_exceeded"
        or news.get("status") == "budget_exceeded"
        or serper.get("status") == "budget_exceeded"
    ):
        return {
            "status": "budget_exceeded",
            "provider": "tavily/serper",
            "query": overview_q,
            "message": (
                serper.get("message")
                if serper.get("status") == "budget_exceeded"
                else tavily_message
            ),
            "company_overview": "",
            "recent_news": "",
            "growth_signals": [],
            "tech_stack": [],
            "sources": [],
            "search_results": [],
        }

    return {
        "status": "error",
        "provider": "tavily/serper",
        "query": overview_q,
        "message": serper.get("message") or tavily_message or "Search failed.",
        "company_overview": "",
        "recent_news": "",
        "growth_signals": [],
        "tech_stack": [],
        "sources": [],
        "search_results": [],
    }


def company_research(company_name: str, industry: str) -> dict:
    """Search the web for information about a company.

    Gathers company overview, recent news, growth signals, and tech stack
    hints from public web sources. Results are cached for 24 hours.

    Args:
        company_name: The company to research (e.g. "TechNova Solutions").
        industry: The company's industry (e.g. "SaaS") — improves search quality.

    Returns:
        dict with status, provider, company_overview, recent_news,
        growth_signals, tech_stack, sources, search_results, official_website,
        and detailed_summary (live mode).
    """
    query = f"{company_name} {industry} company funding news technology"
    cache_key = f"company::{company_name}::{industry}"

    cached = cache.get("company_research", cache_key)
    if cached:
        provider = cached.get("provider")
        # In mock mode, ignore previously cached live data.
        if settings.mock_mode and provider != "mock":
            cached = None
        # In live mode, ignore previously cached mock data.
        elif not settings.mock_mode and provider == "mock":
            cached = None
        else:
            return cached

    if settings.mock_mode:
        mock = _mock_research.mock_company_research(company_name)
        if mock:
            result = _normalize_results(mock)
            cache.put("company_research", cache_key, result)
            return result
        return {
            "status": "not_found",
            "provider": "mock",
            "query": query,
            "message": f"No mock research data for '{company_name}'.",
            "company_overview": "",
            "recent_news": "",
            "growth_signals": [],
            "tech_stack": [],
            "sources": [],
            "search_results": [],
        }

    result = _live_research(company_name, industry)
    if result["status"] == "success":
        cache.put("company_research", cache_key, result)
    return result
