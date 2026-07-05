"""Deterministic lead scoring — pure Python, zero LLM cost (MASTER.md A7).

Exposed as an ADK tool (`lead_score`) and called directly by qualification_service.
"""

from app.skills.qualification_skill import (
    DECISION_MAKER_TITLES,
    ICP_INDUSTRY_SCORES,
    TIER_THRESHOLDS,
)
from app.utils.logger import get_logger

log = get_logger("lead_score")

MAX_FACTOR = 20


def _score_industry(industry: str) -> int:
    return ICP_INDUSTRY_SCORES.get(industry.strip(), 10)


def _score_company_size(company_size: str) -> int:
    try:
        size = int(company_size)
    except (TypeError, ValueError):
        return 8

    if 100 <= size <= 2000:
        return 19
    if 50 <= size < 100 or 2000 < size <= 5000:
        return 16
    if 25 <= size < 50:
        return 11
    if 10 <= size < 25:
        return 6
    return 4


def _score_engagement(title: str, notes: str) -> int:
    title_l = title.lower()
    notes_l = notes.lower()
    score = 0

    if any(t in title_l for t in DECISION_MAKER_TITLES):
        score += 9
    elif "manager" in title_l:
        score += 5
    else:
        score += 3

    if any(k in notes_l for k in ("demo", "pricing", "walkthrough")):
        score += 9
    if any(k in notes_l for k in ("security", "enterprise", "compliance", "soc")):
        score += 8
    if "enterprise" in notes_l:
        score += 4
    if "referr" in notes_l:
        score += 9
    if "whitepaper" in notes_l or "download" in notes_l:
        score += 5
    if "cold" in notes_l or "contact form" in notes_l:
        score += 2
    if "webinar" in notes_l:
        score += 4

    return min(MAX_FACTOR, score)


def _score_growth_signals(count: int) -> int:
    if count >= 3:
        return 18
    if count == 2:
        return 14
    if count == 1:
        return 10
    return 5


def _score_online_presence(source_count: int, tech_count: int, has_website: bool) -> int:
    score = min(10, source_count * 3) + min(8, tech_count * 2)
    if has_website:
        score += 3
    return min(MAX_FACTOR, score)


def _tier_from_score(score: int) -> str:
    if score >= TIER_THRESHOLDS["Hot"]:
        return "Hot"
    if score >= TIER_THRESHOLDS["Warm"]:
        return "Warm"
    return "Cold"


def _confidence(score: int, source_count: int, growth_count: int) -> float:
    base = 0.62
    if source_count >= 2:
        base += 0.12
    if growth_count >= 2:
        base += 0.10
    if score >= 75 or score <= 45:
        base += 0.08
    return round(min(0.98, base), 2)


def compute_lead_score(
    industry: str,
    company_size: str,
    title: str,
    notes: str,
    growth_signal_count: int,
    source_count: int,
    tech_stack_count: int,
    has_website: bool,
) -> dict:
    """Core scoring logic — used by the tool and qualification_service."""
    breakdown = {
        "industry_fit": _score_industry(industry),
        "company_size": _score_company_size(company_size),
        "engagement": _score_engagement(title, notes),
        "growth_signals": _score_growth_signals(growth_signal_count),
        "online_presence": _score_online_presence(source_count, tech_stack_count, has_website),
    }
    score = sum(breakdown.values())

    # Strong buying intent bonus (security review, demo request, referral)
    notes_l = notes.lower()
    title_l = title.lower()
    if any(t in title_l for t in DECISION_MAKER_TITLES) and any(
        k in notes_l for k in ("security", "demo", "pricing", "referr")
    ):
        score += 10

    # Penalize poor ICP fit (small companies in non-target industries)
    if breakdown["industry_fit"] <= 8:
        score -= 6
    if breakdown["company_size"] <= 8:
        score -= 4

    score = max(0, min(100, score))

    # Healthcare leads without enterprise/security signals — longer procurement cycles
    if industry.strip() == "Healthcare" and not any(
        k in notes_l for k in ("security", "enterprise", "compliance")
    ):
        score = min(score, 74)
    tier = _tier_from_score(score)
    confidence = _confidence(score, source_count, growth_signal_count)

    log.info("scored lead: %d -> %s (confidence %.2f)", score, tier, confidence)

    return {
        "status": "success",
        "score": score,
        "tier": tier,
        "confidence": confidence,
        "score_breakdown": breakdown,
    }


def build_reasoning(lead: dict, score_result: dict, research_summary: dict | None) -> str:
    """Template-based reasoning — no LLM required."""
    name = lead.get("name", "Lead")
    title = lead.get("title", "")
    company = lead.get("company", "")
    notes = lead.get("notes", "")
    score = score_result["score"]
    tier = score_result["tier"]
    bd = score_result["score_breakdown"]

    parts = [
        f"{name} ({title}) at {company} scored {score}/100 — tier {tier}."
    ]

    if bd["engagement"] >= 14:
        parts.append(f"Strong buying signal in CRM notes: \"{notes}\".")
    elif bd["engagement"] >= 8:
        parts.append(f"Moderate engagement: \"{notes}\".")
    else:
        parts.append("Limited engagement signals so far.")

    if bd["industry_fit"] >= 16:
        parts.append(f"{lead.get('industry', 'Industry')} is a top-fit vertical for our ICP.")
    elif bd["industry_fit"] <= 8:
        parts.append(f"{lead.get('industry', 'Industry')} is outside our core ICP.")

    if research_summary and research_summary.get("growth_signals"):
        signals = research_summary["growth_signals"][:3]
        parts.append(f"Research found growth signals: {', '.join(signals)}.")

    if bd["company_size"] >= 16:
        parts.append(f"Company size ({lead.get('company_size', '?')} employees) fits our target band.")
    elif bd["company_size"] <= 8:
        parts.append(f"Company size ({lead.get('company_size', '?')} employees) is below ideal range.")

    return " ".join(parts)


def lead_score(
    industry: str,
    company_size: str,
    title: str,
    notes: str,
    growth_signal_count: int,
    source_count: int,
    tech_stack_count: int,
    has_website: str,
) -> dict:
    """Calculate a deterministic lead score from CRM and research data.

    Each factor scores 0–20 (max total 100). Tier: Hot ≥75, Warm ≥55, Cold <55.
    Use after research is complete — pass counts from the research findings.

    Args:
        industry: Company industry from CRM (e.g. "SaaS", "Fintech").
        company_size: Employee count as string (e.g. "250").
        title: Lead's job title (e.g. "VP of Sales").
        notes: CRM engagement notes (e.g. "Requested pricing demo").
        growth_signal_count: Number of growth signals found in research.
        source_count: Number of research source URLs found.
        tech_stack_count: Number of technologies identified.
        has_website: "true" if company website was analyzed, else "false".

    Returns:
        dict with status, score (0-100), tier (Hot/Warm/Cold), confidence (0-1),
        and score_breakdown with five factor scores.
    """
    website = has_website.strip().lower() in ("true", "1", "yes")
    result = compute_lead_score(
        industry=industry,
        company_size=company_size,
        title=title,
        notes=notes,
        growth_signal_count=growth_signal_count,
        source_count=source_count,
        tech_stack_count=tech_stack_count,
        has_website=website,
    )
    result["reasoning_hint"] = (
        f"Score {result['score']}/100 → {result['tier']}. "
        f"Strongest factors: {', '.join(k for k, v in result['score_breakdown'].items() if v >= 16)}."
    )
    return result
