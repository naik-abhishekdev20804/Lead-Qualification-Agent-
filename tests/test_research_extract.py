"""Tests for research extraction helpers — deterministic, no API calls."""

from app.mcp_tools import _research_extract as extract


class TestPlaceholderUrl:
    def test_example_com_is_placeholder(self):
        assert extract.is_placeholder_url("https://technova.example.com") is True

    def test_real_url_not_placeholder(self):
        assert extract.is_placeholder_url("https://stripe.com") is False

    def test_empty_is_placeholder(self):
        assert extract.is_placeholder_url("") is True


class TestExtractTechStack:
    def test_finds_known_tools(self):
        text = "They use Salesforce, HubSpot, and AWS for their GTM stack."
        stack = extract.extract_tech_stack(text)
        assert "Salesforce" in stack
        assert "HubSpot" in stack
        assert "AWS" in stack


class TestExtractGrowthSignals:
    def test_funding_and_hiring(self):
        text = "Company raised $30M Series B and is hiring 12 sales roles."
        signals = extract.extract_growth_signals(text)
        assert any("Funding" in s or "funding" in s.lower() for s in signals)
        assert any("hiring" in s.lower() for s in signals)


class TestDiscoverWebsite:
    def test_picks_company_domain(self):
        results = [
            {"url": "https://www.linkedin.com/company/technova", "title": "LinkedIn"},
            {"url": "https://technova.io/about", "title": "About TechNova"},
            {"url": "https://news.example.com/article", "title": "News"},
        ]
        url = extract.discover_official_website("TechNova Solutions", results)
        assert url == "https://technova.io"

    def test_skips_social_domains(self):
        results = [{"url": "https://www.linkedin.com/company/acme", "title": "LI"}]
        assert extract.discover_official_website("Acme Corp", results) is None


class TestBuildDetailedSummary:
    def test_includes_sections(self):
        summary = extract.build_detailed_summary(
            overview="A SaaS company.",
            news="Raised Series B.",
            growth_signals=["Hiring"],
            tech_stack=["AWS"],
            headings=["Products", "Pricing"],
            website_excerpt="Welcome to our platform.",
        )
        assert "## Overview" in summary
        assert "## Recent news" in summary
        assert "AWS" in summary
