"""Setup sanity tests — code correctness only, no LLM calls.

Agent *behavior* is validated via ADK eval (evaluation/), never pytest.
"""

from app.mcp_tools.crm_lookup_tool import crm_lookup
from app.utils import api_budget, cache
from config import settings


class TestConfig:
    def test_settings_load(self):
        assert settings.gemini_model
        assert settings.daily_api_budget > 0

    def test_mock_mode_defaults_on(self):
        assert settings.mock_mode is True


class TestAgentDefinition:
    def test_root_agent_importable(self):
        from app.agent import root_agent

        assert root_agent.name == "lead_qualification_orchestrator"
        assert len(root_agent.tools) >= 9

    def test_outreach_agent_importable(self):
        from app.agents.outreach_agent import create_outreach_agent

        agent = create_outreach_agent()
        assert agent.name == "outreach_agent"
        assert len(agent.tools) == 1

    def test_full_pipeline_importable(self):
        from app.agent import create_full_pipeline

        pipeline = create_full_pipeline()
        assert pipeline.name == "full_pipeline"
        assert len(pipeline.sub_agents) == 3

    def test_qualification_agent_importable(self):
        from app.agents.qualification_agent import create_qualification_agent

        agent = create_qualification_agent()
        assert agent.name == "qualification_agent"
        assert len(agent.tools) == 1

    def test_research_agent_importable(self):
        from app.agents.research_agent import create_research_agent

        agent = create_research_agent()
        assert agent.name == "research_agent"
        assert len(agent.tools) == 3

    def test_qualify_pipeline_importable(self):
        from app.agent import create_qualify_pipeline

        pipeline = create_qualify_pipeline()
        assert pipeline.name == "qualify_pipeline"
        assert len(pipeline.sub_agents) == 2

    def test_mcp_server_importable(self):
        from app.mcp_server.server import mcp

        assert mcp.name == "leadpilot"


class TestCrmLookupTool:
    def test_lookup_by_id(self):
        result = crm_lookup("L-001")
        assert result["status"] == "success"
        assert result["leads"][0]["company"] == "Stripe"

    def test_lookup_by_company(self):
        result = crm_lookup("stripe")
        assert result["status"] == "success"
        assert result["leads"][0]["company"] == "Stripe"

    def test_lookup_all(self):
        result = crm_lookup("all")
        assert len(result["leads"]) == 4

    def test_lookup_no_match(self):
        result = crm_lookup("does-not-exist-xyz")
        assert result["status"] == "not_found"
        assert result["leads"] == []


class TestCache:
    def test_roundtrip(self):
        cache.put("test_provider", "some query", {"answer": 42})
        assert cache.get("test_provider", "some query") == {"answer": 42}

    def test_miss(self):
        assert cache.get("test_provider", "never stored") is None

    def test_key_normalization(self):
        cache.put("test_provider", "  TechNova  ", {"v": 1})
        assert cache.get("test_provider", "technova") == {"v": 1}


class TestApiBudget:
    def test_consume_and_remaining(self):
        before = api_budget.remaining("test_budget_provider")
        api_budget.consume("test_budget_provider")
        assert api_budget.remaining("test_budget_provider") == before - 1

    def test_report_shape(self):
        report = api_budget.usage_report()
        assert "used" in report and "remaining" in report
