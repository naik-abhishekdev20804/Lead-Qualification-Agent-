"""Outreach tests — deterministic recommendations and emails only, no LLM calls."""

from app.mcp_tools.outreach_tool import (
    build_recommendation,
    draft_follow_up_email,
    generate_outreach,
)
from app.services.outreach_service import run_lead_outreach
from app.services.qualification_service import run_lead_qualification
from app.services.research_service import run_lead_research

EXPECTED_TIERS_MINIMAL = {
    "L-001": "Cold",
    "L-002": "Cold",
    "L-003": "Cold",
    "L-004": "Cold",
}


class TestOutreachTool:
    def test_hot_lead_gets_draft_email(self):
        lead = {
            "name": "",
            "company": "HubSpot",
            "title": "",
            "industry": "SaaS",
            "notes": "Asked about security compliance",
        }
        qual = {"tier": "Hot", "score": 82, "research_summary": {"growth_signals": []}}
        rec = build_recommendation(lead, qual)
        draft = draft_follow_up_email(lead, qual, rec)
        assert draft is not None
        assert draft["status"] == "pending_approval"
        assert draft["body"].startswith("Hi HubSpot,")
        assert "Thank you for reaching out." in draft["body"]
        assert "Regards,\nSales Team" in draft["body"]

    def test_cold_lead_no_draft_email(self):
        lead = {
            "name": "",
            "company": "Notion",
            "title": "",
            "industry": "SaaS",
            "notes": "Downloaded whitepaper",
        }
        qual = {"tier": "Cold", "score": 38, "research_summary": {}}
        rec = build_recommendation(lead, qual)
        draft = draft_follow_up_email(lead, qual, rec)
        assert draft is None
        assert rec["priority"] == 4

    def test_recommendation_priority_by_tier(self):
        hot = build_recommendation(
            {"name": "", "company": "Stripe", "notes": ""},
            {"tier": "Hot", "score": 90, "research_summary": {}},
        )
        warm = build_recommendation(
            {"name": "", "company": "Shopify", "notes": ""},
            {"tier": "Warm", "score": 60, "research_summary": {}},
        )
        assert hot["priority"] <= warm["priority"]

    def test_adk_tool_wrapper(self):
        result = generate_outreach(
            lead_name="",
            company="HubSpot",
            title="",
            industry="SaaS",
            tier="Warm",
            score=65,
            notes="Security inquiry",
            reasoning="Strong fit",
            recent_news="",
            growth_signals="",
        )
        assert result["status"] == "success"
        assert result["draft_email"]["status"] == "pending_approval"


class TestOutreachService:
    def test_run_lead_outreach_minimal_crm(self):
        for lead_id, expected_tier in EXPECTED_TIERS_MINIMAL.items():
            result = run_lead_outreach(lead_id)
            assert result["status"] == "success", lead_id
            assert result["qualification"]["tier"] == expected_tier

    def test_enriched_research_enables_draft_email(self):
        research = run_lead_research("L-003")
        research["research_summary"]["growth_signals"] = ["Funding", "Hiring", "Expansion"]
        research["research_summary"]["tech_stack"] = ["AWS", "HubSpot"]
        research["research_summary"]["sources"] = ["https://hubspot.com", "https://news.com"]
        qual = run_lead_qualification("L-003", research_result=research)
        result = run_lead_outreach("L-003", qualification_result=qual)
        assert result["qualification"]["score"] >= 55
        assert result["draft_email"] is not None

    def test_shape_matches_ui(self):
        result = run_lead_outreach("L-003")
        qual = result["qualification"]
        for key in (
            "score", "tier", "confidence", "recommendation",
            "draft_email", "timeline", "final_report", "outreach_live",
        ):
            assert key in qual

    def test_reuses_qualification_result(self):
        qual_only = run_lead_qualification("L-004")
        result = run_lead_outreach("L-004", qualification_result=qual_only)
        assert result["status"] == "success"
        assert result["qualification"]["outreach_live"] is True

    def test_not_found(self):
        result = run_lead_outreach("L-999")
        assert result["status"] == "not_found"
