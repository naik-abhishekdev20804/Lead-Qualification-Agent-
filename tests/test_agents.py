"""Research tool tests — deterministic only, no LLM calls."""

import app.mcp_tools.company_research_tool as company_research_tool
import app.mcp_tools.website_analysis_tool as website_analysis_tool
from app.mcp_tools.company_research_tool import company_research
from app.mcp_tools.website_analysis_tool import website_analysis
from app.services.research_service import run_lead_research
from app.utils import cache
from config import settings

CRM_COMPANIES = [
    ("Stripe", "Fintech"),
    ("Notion", "SaaS"),
    ("HubSpot", "SaaS"),
    ("Shopify", "E-commerce"),
]


class TestCompanyResearchTool:
    def test_mock_mode_returns_stripe_stub(self):
        assert settings.mock_mode is True
        result = company_research("Stripe", "Fintech")
        assert result["status"] == "success"
        assert "Tavily" in result["company_overview"]

    def test_mock_mode_unknown_company(self):
        result = company_research("Unknown Corp XYZ", "Tech")
        assert result["status"] == "not_found"

    def test_cache_hit_on_second_call(self):
        cache.put(
            "company_research",
            "company::Zebra Test Co::Test",
            {
                "status": "success",
                "provider": "mock",
                "query": "x",
                "company_overview": "from cache",
                "recent_news": "",
                "growth_signals": [],
                "tech_stack": [],
                "sources": [],
                "search_results": [],
            },
        )
        result = company_research("Zebra Test Co", "Test")
        assert result["provider"] == "mock"
        assert result["company_overview"] == "from cache"

    def test_all_crm_companies_have_mock_stubs(self):
        for company, industry in CRM_COMPANIES:
            result = company_research(company, industry)
            assert result["status"] == "success", f"Missing mock stub for {company}"

    def test_live_mode_ignores_cached_mock_entry(self, monkeypatch):
        old_mode = settings.mock_mode
        settings.mock_mode = False
        try:
            key = "company::Cache Bypass Co::Testing"
            cache.put(
                "company_research",
                key,
                {
                    "status": "success",
                    "provider": "mock",
                    "query": "mock",
                    "company_overview": "mock cached",
                    "recent_news": "",
                    "growth_signals": [],
                    "tech_stack": [],
                    "sources": [],
                    "search_results": [],
                },
            )

            monkeypatch.setattr(
                company_research_tool,
                "_live_research",
                lambda company_name, industry: {
                    "status": "success",
                    "provider": "tavily",
                    "query": f"{company_name} {industry}",
                    "company_overview": "live overview",
                    "recent_news": "live news",
                    "growth_signals": [],
                    "tech_stack": [],
                    "sources": ["https://example.org/live"],
                    "search_results": [],
                    "official_website": "https://cachebypass.example",
                    "detailed_summary": "live",
                    "tavily_answer": "",
                },
            )

            result = company_research("Cache Bypass Co", "Testing")
            assert result["provider"] == "tavily"
            assert result["company_overview"] == "live overview"
        finally:
            settings.mock_mode = old_mode


class TestWebsiteAnalysisTool:
    def test_mock_mode_unknown_url_without_crm_website(self):
        result = website_analysis("https://stripe.com")
        assert result["status"] == "not_found"

    def test_normalizes_url_without_scheme(self):
        result = website_analysis("stripe.com")
        assert result["status"] == "not_found"

    def test_live_mode_ignores_cached_mock_entry(self, monkeypatch):
        old_mode = settings.mock_mode
        settings.mock_mode = False
        try:
            cache.put(
                "website_analysis",
                "https://cache-bypass-site.test",
                {
                    "status": "success",
                    "provider": "mock",
                    "url": "https://cache-bypass-site.test",
                    "title": "mock",
                    "description": "mock",
                    "headings": [],
                    "tech_hints": [],
                },
            )

            monkeypatch.setattr(
                website_analysis_tool,
                "_scrape_live",
                lambda url: {
                    "status": "success",
                    "provider": "firecrawl",
                    "url": url,
                    "title": "live title",
                    "description": "live description",
                    "headings": ["Overview"],
                    "tech_hints": ["AWS"],
                    "raw_excerpt": "live",
                    "page_summary": "live summary",
                },
            )

            result = website_analysis("https://cache-bypass-site.test")
            assert result["provider"] == "firecrawl"
            assert result["title"] == "live title"
        finally:
            settings.mock_mode = old_mode


class TestResearchService:
    def test_run_lead_research_l001(self):
        result = run_lead_research("L-001")
        assert result["status"] == "success"
        assert result["lead"]["company"] == "Stripe"
        summary = result["research_summary"]
        assert summary["company_overview"]
        assert result["mock"] is True

    def test_run_lead_research_all_leads(self):
        for lead_id in ("L-001", "L-002", "L-003", "L-004"):
            result = run_lead_research(lead_id)
            assert result["status"] == "success", lead_id

    def test_run_lead_research_not_found(self):
        result = run_lead_research("L-999")
        assert result["status"] == "not_found"

    def test_research_summary_shape_matches_ui(self):
        result = run_lead_research("L-003")
        summary = result["research_summary"]
        for key in (
            "company_overview",
            "recent_news",
            "growth_signals",
            "tech_stack",
            "sources",
            "detailed_summary",
            "official_website",
        ):
            assert key in summary

    def test_crm_has_minimum_fields_only(self):
        result = run_lead_research("L-001")
        lead = result["lead"]
        assert lead["company"] == "Stripe"
        assert lead["industry"] == "Fintech"
        assert lead["notes"]
        assert not lead.get("website")
