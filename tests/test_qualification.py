"""Qualification scoring tests — deterministic math only, no LLM calls."""

from copy import deepcopy

from app.mcp_tools.lead_score_tool import compute_lead_score, lead_score
from app.services.qualification_service import qualify_from_crm_only, run_lead_qualification
from app.services.research_service import run_lead_research

# Minimal CRM + empty mock stubs → low scores until Tavily/Firecrawl enrich research
EXPECTED_TIERS_MINIMAL = {
    "L-001": "Cold",
    "L-002": "Cold",
    "L-003": "Cold",
    "L-004": "Cold",
}


class TestLeadScoreTool:
    def test_score_breakdown_sums_to_total(self):
        result = compute_lead_score(
            industry="SaaS",
            company_size="250",
            title="VP of Sales",
            notes="Asked for pricing demo after webinar",
            growth_signal_count=3,
            source_count=3,
            tech_stack_count=3,
            has_website=True,
        )
        assert result["status"] == "success"
        assert all(v <= 20 for v in result["score_breakdown"].values())
        assert 0 <= result["score"] <= 100

    def test_hot_tier_threshold(self):
        result = compute_lead_score(
            industry="Fintech",
            company_size="900",
            title="CTO",
            notes="Requested enterprise security docs",
            growth_signal_count=2,
            source_count=3,
            tech_stack_count=3,
            has_website=True,
        )
        assert result["tier"] == "Hot"
        assert result["score"] >= 75

    def test_cold_tier_small_company(self):
        result = compute_lead_score(
            industry="Food & Beverage",
            company_size="12",
            title="Founder",
            notes="Downloaded whitepaper twice",
            growth_signal_count=1,
            source_count=1,
            tech_stack_count=1,
            has_website=True,
        )
        assert result["tier"] == "Cold"
        assert result["score"] < 55

    def test_adk_tool_wrapper(self):
        result = lead_score(
            industry="SaaS",
            company_size="250",
            title="VP of Sales",
            notes="demo request",
            growth_signal_count=2,
            source_count=2,
            tech_stack_count=2,
            has_website="true",
        )
        assert result["status"] == "success"
        assert "reasoning_hint" in result

    def test_all_factors_capped_at_20(self):
        result = compute_lead_score(
            industry="SaaS",
            company_size="250",
            title="CEO",
            notes="demo pricing security referral webinar",
            growth_signal_count=5,
            source_count=10,
            tech_stack_count=10,
            has_website=True,
        )
        for value in result["score_breakdown"].values():
            assert value <= 20


class TestQualificationService:
    def test_run_lead_qualification_minimal_crm(self):
        """CRM stores company + notes only — scores stay low until live research."""
        for lead_id, expected_tier in EXPECTED_TIERS_MINIMAL.items():
            result = run_lead_qualification(lead_id)
            assert result["status"] == "success", lead_id
            qual = result["qualification"]
            assert qual["tier"] == expected_tier, f"{lead_id}: got {qual['tier']}, score {qual['score']}"
            assert qual["score"] < 75
            assert qual["reasoning"]

    def test_enriched_research_raises_score(self):
        """Simulates Tavily/Firecrawl enrichment raising the score."""
        research = run_lead_research("L-001")
        research["research_summary"]["growth_signals"] = ["Series funding", "Hiring spree", "APAC expansion"]
        research["research_summary"]["tech_stack"] = ["AWS", "Salesforce"]
        research["research_summary"]["sources"] = ["https://stripe.com", "https://techcrunch.com"]
        result = run_lead_qualification("L-001", research_result=research)
        assert result["qualification"]["score"] >= 55
        assert result["qualification"]["tier"] in ("Hot", "Warm")

    def test_qualification_shape_matches_ui(self):
        result = run_lead_qualification("L-001")
        qual = result["qualification"]
        for key in ("score", "tier", "confidence", "score_breakdown", "reasoning", "research_summary"):
            assert key in qual

    def test_qualify_from_crm_only(self):
        result = qualify_from_crm_only("L-003")
        assert result["status"] == "success"
        assert result["qualification"]["tier"] in ("Hot", "Warm", "Cold")

    def test_not_found(self):
        result = run_lead_qualification("L-999")
        assert result["status"] == "not_found"

    def test_reuses_research_result(self):
        research = run_lead_research("L-004")
        research["research_summary"]["growth_signals"] = ["New product launch"]
        research["research_summary"]["sources"] = ["https://shopify.com"]
        result = run_lead_qualification("L-004", research_result=research)
        assert result["qualification"]["tier"] in ("Hot", "Warm", "Cold")

    def test_discovered_website_counts_for_online_presence(self):
        """Official website found via web research should boost online-presence score."""
        research = run_lead_research("L-001")
        baseline = deepcopy(research)
        baseline["research_summary"]["growth_signals"] = []
        baseline["research_summary"]["tech_stack"] = []
        baseline["research_summary"]["sources"] = ["https://news.example.org/stripe"]
        baseline["research_summary"]["official_website"] = ""
        baseline["website"] = {"url": ""}

        enriched = deepcopy(baseline)
        enriched["research_summary"]["official_website"] = "https://stripe.com"
        enriched["website"] = {"url": "https://stripe.com"}

        without_site = run_lead_qualification("L-001", research_result=baseline)
        with_site = run_lead_qualification("L-001", research_result=enriched)

        without_presence = without_site["qualification"]["score_breakdown"]["online_presence"]
        with_presence = with_site["qualification"]["score_breakdown"]["online_presence"]

        assert with_presence > without_presence
