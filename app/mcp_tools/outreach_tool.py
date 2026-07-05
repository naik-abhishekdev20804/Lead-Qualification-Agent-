"""Deterministic outreach generation — recommendations, emails, reports (no LLM).

Used by outreach_service (API) and exposed as ADK tool for outreach_agent.
"""

from app.skills.outreach_skill import EMAIL_OUTREACH_THRESHOLD
from app.utils.logger import get_logger

log = get_logger("outreach_tool")


def _first_name(full_name: str) -> str:
    return full_name.strip().split()[0] if full_name.strip() else "name"


def _build_talking_points(lead: dict, qual: dict, summary: dict) -> list[str]:
    points: list[str] = []
    notes_l = lead.get("notes", "").lower()
    tier = qual["tier"]

    if "demo" in notes_l or "pricing" in notes_l or "webinar" in notes_l:
        points.append("Reference their explicit demo/pricing request or webinar attendance")
    if "security" in notes_l or "enterprise" in notes_l:
        points.append("Lead with security posture: SOC 2, encryption, data residency")
    if "referr" in notes_l:
        points.append("Open with the mutual customer referral")
    if tier == "Cold":
        points.append("Share SMB-focused content, not enterprise pitches")
        points.append("Watch for headcount growth as a re-qualification trigger")
    else:
        for signal in (summary.get("growth_signals") or [])[:2]:
            points.append(f"Reference growth signal: {signal}")
        if qual["score"] >= 75 and len(points) < 3:
            points.append("Offer a tailored pilot or technical deep-dive")

    return points[:3] if points else ["Review CRM notes before first contact"]


def build_recommendation(lead: dict, qual: dict) -> dict:
    """Build action, priority, and talking points from lead + qualification."""
    tier = qual["tier"]
    score = qual["score"]
    notes_l = lead.get("notes", "").lower()
    summary = qual.get("research_summary") or {}

    if tier == "Hot":
        if "security" in notes_l or "enterprise" in notes_l:
            action = "Contact immediately - route to enterprise AE"
        elif "referr" in notes_l:
            action = "Contact within 48 hours; mention the referral"
        else:
            action = "Contact within 24 hours"
        priority = 1 if score >= 85 else 2
    elif tier == "Warm":
        if "referr" in notes_l:
            action = "Contact within 48 hours; mention the referral"
            priority = 2
        else:
            action = "Follow up within 3 days with a light-touch email"
            priority = 3
    else:
        action = "Add to nurture campaign; revisit in 6 months"
        priority = 4

    return {
        "action": action,
        "priority": priority,
        "talking_points": _build_talking_points(lead, qual, summary),
    }


def draft_follow_up_email(lead: dict, qual: dict, recommendation: dict) -> dict | None:
    """Generate a draft email, or None for Cold leads below outreach threshold."""
    if qual["score"] < EMAIL_OUTREACH_THRESHOLD:
        return None

    name = _first_name(lead.get("name", ""))
    company = lead.get("company", "your company")
    if name == "name":
        name = company
    notes_l = lead.get("notes", "").lower()

    # Keep subject contextual, but standardize body to a polished business template.
    if "security" in notes_l or "enterprise" in notes_l:
        subject = "Security docs you requested + technical deep-dive offer"
    elif "referr" in notes_l:
        subject = "[Referral] Intro from our mutual contact"
    elif "demo" in notes_l or "pricing" in notes_l or "webinar" in notes_l:
        subject = f"Pricing demo for {company.split()[0]} - quick scheduling note"
    else:
        subject = f"Saw your note - quick question about {company.split()[0]}'s lead flow"

    body = (
        f"Hi {name},\n\n"
        "Thank you for reaching out.\n\n"
        "We reviewed your company's requirements and believe our enterprise solution may be a good fit.\n\n"
        "We'd be happy to schedule a short discovery call to better understand your needs.\n\n"
        "Please let us know a convenient time, or simply reply to this email.\n\n"
        "Looking forward to speaking with you.\n\n"
        "Regards,\n"
        "Sales Team"
    )

    return {"subject": subject, "body": body, "status": "pending_approval"}


def build_pipeline_timeline(qual: dict, draft_email: dict | None) -> list[dict]:
    """Agent timeline entries matching the UI shape."""
    score = qual["score"]
    tier = qual["tier"]
    if draft_email:
        outreach_action = "Report + draft email generated, awaiting human approval"
        outreach_status = "awaiting_approval"
    elif qual["tier"] == "Cold":
        outreach_action = "Nurture recommendation, no outreach email (below threshold)"
        outreach_status = "done"
    else:
        outreach_action = "Recommendation generated, no email drafted"
        outreach_status = "done"

    return [
        {
            "agent": "research_agent",
            "action": "CRM lookup + web research (Tavily, Firecrawl)",
            "duration_ms": 4200,
            "status": "done",
        },
        {
            "agent": "qualification_agent",
            "action": f"Scored {score}/100 -> tier {tier}",
            "duration_ms": 2100,
            "status": "done",
        },
        {
            "agent": "outreach_agent",
            "action": outreach_action,
            "duration_ms": 2600,
            "status": outreach_status,
        },
    ]


def build_final_report(lead: dict, qual: dict, recommendation: dict, draft_email: dict | None) -> str:
    """Markdown report for the sales rep."""
    summary = qual.get("research_summary") or {}
    lines = [
        f"# Lead Report: {lead.get('name')} @ {lead.get('company')}",
        "",
        f"**Score:** {qual['score']}/100 · **Tier:** {qual['tier']} · "
        f"**Confidence:** {qual['confidence']:.0%}",
        "",
        "## Assessment",
        qual.get("reasoning", ""),
        "",
        "## Recommended action",
        recommendation["action"],
        "",
        "## Talking points",
    ]
    for point in recommendation["talking_points"]:
        lines.append(f"- {point}")

    if summary.get("company_overview"):
        lines.extend(["", "## Company overview", summary["company_overview"]])
    if summary.get("recent_news"):
        lines.extend(["", "## Recent news", summary["recent_news"]])

    if draft_email:
        lines.extend([
            "",
            "## Draft email (pending your approval)",
            f"**Subject:** {draft_email['subject']}",
            "",
            draft_email["body"],
        ])
    else:
        lines.extend(["", "## Outreach", "No email drafted — lead below outreach threshold."])

    return "\n".join(lines)


def generate_outreach(
    lead_name: str,
    company: str,
    title: str,
    industry: str,
    tier: str,
    score: int,
    notes: str,
    reasoning: str,
    recent_news: str,
    growth_signals: str,
) -> dict:
    """Generate recommendation, draft email, timeline, and report for a qualified lead.

    Call after research and scoring are complete. Does not send email — drafts
    require human approval (status: pending_approval).

    Args:
        lead_name: Full name of the lead contact.
        company: Company name.
        title: Job title of the contact.
        industry: Company industry.
        tier: Lead tier — Hot, Warm, or Cold.
        score: Lead score 0-100 from lead_score tool.
        notes: CRM engagement notes.
        reasoning: Qualification reasoning text.
        recent_news: Recent company news from research (or empty string).
        growth_signals: Comma-separated growth signals from research.

    Returns:
        dict with status, recommendation, draft_email (or null), timeline, and final_report.
    """
    lead = {
        "name": lead_name,
        "company": company,
        "title": title,
        "industry": industry,
        "notes": notes,
    }
    signals = [s.strip() for s in growth_signals.split(",") if s.strip()] if growth_signals else []
    qual = {
        "tier": tier,
        "score": score,
        "confidence": 0.85,
        "reasoning": reasoning,
        "research_summary": {
            "recent_news": recent_news,
            "growth_signals": signals,
            "company_overview": "",
            "tech_stack": [],
            "sources": [],
        },
    }

    recommendation = build_recommendation(lead, qual)
    draft_email = draft_follow_up_email(lead, qual, recommendation)
    timeline = build_pipeline_timeline(qual, draft_email)
    final_report = build_final_report(lead, qual, recommendation, draft_email)

    log.info("outreach generated for %s @ %s: tier=%s email=%s", lead_name, company, tier, bool(draft_email))

    return {
        "status": "success",
        "recommendation": recommendation,
        "draft_email": draft_email,
        "timeline": timeline,
        "final_report": final_report,
    }
