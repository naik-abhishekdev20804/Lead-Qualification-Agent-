"""Deterministic outreach — recommendations, emails, reports without an LLM call."""

from app.mcp_tools.outreach_tool import (
    build_final_report,
    build_pipeline_timeline,
    build_recommendation,
    draft_follow_up_email,
)
from app.services.qualification_service import run_lead_qualification
from app.utils.logger import get_logger

log = get_logger("outreach_service")


def run_lead_outreach(lead_id: str, qualification_result: dict | None = None) -> dict:
    """Run full outreach: qualification (if needed) + recommendation + draft email.

    Args:
        lead_id: CRM lead ID (e.g. "L-001").
        qualification_result: Optional pre-computed qualification from run_lead_qualification().

    Returns:
        dict with status, lead, qualification (full UI shape), and outreach fields.
    """
    if qualification_result is None:
        qualification_result = run_lead_qualification(lead_id)

    if qualification_result["status"] != "success":
        return qualification_result

    lead = qualification_result["lead"]
    qual = qualification_result["qualification"]

    recommendation = build_recommendation(lead, qual)
    draft_email = draft_follow_up_email(lead, qual, recommendation)
    timeline = build_pipeline_timeline(qual, draft_email)
    final_report = build_final_report(lead, qual, recommendation, draft_email)

    full_qualification = {
        **qual,
        "recommendation": recommendation,
        "draft_email": draft_email,
        "timeline": timeline,
        "final_report": final_report,
        "outreach_live": True,
    }

    log.info(
        "outreach complete for %s: priority=%s email=%s",
        lead_id,
        recommendation["priority"],
        "yes" if draft_email else "no",
    )

    return {
        "status": "success",
        "lead_id": lead_id,
        "lead": lead,
        "qualification": full_qualification,
        "recommendation": recommendation,
        "draft_email": draft_email,
        "timeline": timeline,
        "final_report": final_report,
        "mock": qualification_result.get("mock", False),
    }
