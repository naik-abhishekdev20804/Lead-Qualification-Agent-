"""MCP server tests — tool wiring and HITL gate only, no stdio transport tests."""

import json

from app.mcp_server.approval_store import approve_draft_email, register_draft
from app.mcp_server.server import (
    mcp,
    mcp_approve_draft_email,
    mcp_crm_lookup,
    mcp_generate_outreach,
    mcp_lead_score,
)


class TestMcpServerDefinition:
    def test_server_importable(self):
        assert mcp.name == "leadpilot"

    def test_tool_count(self):
        tools = mcp._tool_manager.list_tools()  # noqa: SLF001 — test internal registry
        names = {t.name for t in tools}
        assert names == {
            "crm_lookup",
            "company_research",
            "website_analysis",
            "lead_score",
            "generate_outreach",
            "approve_draft_email",
        }


class TestMcpToolWrappers:
    def test_crm_lookup_returns_json(self):
        raw = mcp_crm_lookup("L-001")
        data = json.loads(raw)
        assert data["status"] == "success"
        assert data["leads"][0]["company"] == "Stripe"

    def test_lead_score_returns_json(self):
        raw = mcp_lead_score(
            industry="SaaS",
            company_size="250",
            title="VP of Sales",
            notes="demo request",
            growth_signal_count=2,
            source_count=2,
            tech_stack_count=2,
            has_website="true",
        )
        data = json.loads(raw)
        assert data["status"] == "success"
        assert 0 <= data["score"] <= 100

    def test_generate_outreach_hot_lead(self):
        raw = mcp_generate_outreach(
            lead_name="Priya Sharma",
            company="HubSpot",
            title="VP of Sales",
            industry="SaaS",
            tier="Hot",
            score=88,
            notes="Asked for pricing demo",
            reasoning="Strong fit",
            recent_news="Series B funding",
            growth_signals="hiring, funding",
            lead_id="L-001",
        )
        data = json.loads(raw)
        assert data["status"] == "success"
        assert data["draft_email"]["status"] == "pending_approval"


class TestMcpApprovalGate:
    def test_approve_requires_draft(self):
        result = approve_draft_email("L-999", "approve")
        assert result["status"] == "not_found"

    def test_approve_and_reject_flow(self):
        register_draft(
            "L-001",
            {"subject": "Test", "body": "Hi", "status": "pending_approval"},
        )
        approved = json.loads(mcp_approve_draft_email("L-001", "approve"))
        assert approved["status"] == "success"
        assert approved["email_status"] == "approved_and_sent"
        assert "Simulated send" in approved["note"]

        register_draft(
            "L-002",
            {"subject": "Test", "body": "Hi", "status": "pending_approval"},
        )
        rejected = approve_draft_email("L-002", "reject")
        assert rejected["email_status"] == "rejected"

    def test_invalid_action(self):
        result = approve_draft_email("L-001", "send_now")
        assert result["status"] == "error"
