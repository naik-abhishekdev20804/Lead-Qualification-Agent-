"""Deterministic lead qualification — research + scoring without an LLM call."""

from app.mcp_tools.crm_lookup_tool import crm_lookup
from app.mcp_tools.lead_score_tool import build_reasoning, compute_lead_score
from app.services.research_service import run_lead_research
from app.utils.logger import get_logger

log = get_logger("qualification_service")


def _has_real_website(*urls: str) -> bool:
    """True when at least one website URL is present and non-placeholder."""
    for candidate in urls:
        lower = (candidate or "").strip().lower()
        if lower and "example.com" not in lower and lower not in ("http://", "https://", "n/a", "none"):
            return True
    return False


def run_lead_qualification(lead_id: str, research_result: dict | None = None) -> dict:
    """Run research (if needed) then deterministic scoring for one lead.

    Args:
        lead_id: CRM lead ID (e.g. "L-001").
        research_result: Optional pre-computed research from run_lead_research().

    Returns:
        dict with status, lead_id, lead, research_summary, qualification block
        (score, tier, confidence, score_breakdown, reasoning), and mock flag.
    """
    if research_result is None:
        research_result = run_lead_research(lead_id)

    if research_result["status"] != "success":
        return research_result

    lead = research_result["lead"]
    summary = research_result["research_summary"]
    website = research_result.get("website") or {}
    has_website = _has_real_website(
        summary.get("official_website", ""),
        website.get("url", ""),
        lead.get("website", ""),
    )

    score_result = compute_lead_score(
        industry=lead.get("industry", ""),
        company_size=lead.get("company_size") or "",
        title=lead.get("title") or "",
        notes=lead.get("notes", ""),
        growth_signal_count=len(summary.get("growth_signals") or []),
        source_count=len(summary.get("sources") or []),
        tech_stack_count=len(summary.get("tech_stack") or []),
        has_website=has_website,
    )

    reasoning = build_reasoning(lead, score_result, summary)

    qualification = {
        "lead_id": lead_id,
        "mock": research_result.get("mock", False),
        "score": score_result["score"],
        "tier": score_result["tier"],
        "confidence": score_result["confidence"],
        "score_breakdown": score_result["score_breakdown"],
        "reasoning": reasoning,
        "research_summary": summary,
        "qualification_live": True,
    }

    log.info("qualification complete for %s: %d -> %s", lead_id, score_result["score"], score_result["tier"])

    return {
        "status": "success",
        "lead_id": lead_id,
        "lead": lead,
        "research_summary": summary,
        "qualification": qualification,
        "mock": research_result.get("mock", False),
    }


def qualify_from_crm_only(lead_id: str) -> dict:
    """Score a lead using CRM data only (no web research). Useful for quick checks."""
    crm = crm_lookup(lead_id)
    if crm["status"] != "success":
        return {"status": "not_found", "lead_id": lead_id, "message": f"Lead '{lead_id}' not in CRM."}

    lead = crm["leads"][0]
    empty_summary: dict = {
        "company_overview": "",
        "recent_news": "",
        "growth_signals": [],
        "tech_stack": [],
        "sources": [],
    }

    score_result = compute_lead_score(
        industry=lead.get("industry", ""),
        company_size=lead.get("company_size") or "",
        title=lead.get("title") or "",
        notes=lead.get("notes", ""),
        growth_signal_count=0,
        source_count=0,
        tech_stack_count=0,
        has_website=bool(lead.get("website")),
    )

    reasoning = build_reasoning(lead, score_result, empty_summary)

    return {
        "status": "success",
        "lead_id": lead_id,
        "lead": lead,
        "qualification": {
            "lead_id": lead_id,
            "mock": False,
            "score": score_result["score"],
            "tier": score_result["tier"],
            "confidence": max(0.55, score_result["confidence"] - 0.15),
            "score_breakdown": score_result["score_breakdown"],
            "reasoning": reasoning + " (Scored from CRM only — run full research for higher confidence.)",
            "research_summary": empty_summary,
            "qualification_live": True,
        },
    }
