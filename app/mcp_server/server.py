"""LeadPilot MCP server — stdio transport for Cursor, Claude Desktop, and ADK clients.

Wraps the same deterministic tools used by the ADK agents (app/mcp_tools/).
CRM is read-only. Outreach drafts require human approval — no send tool exists.
"""

import json

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

from app.mcp_server.approval_store import approve_draft_email  # noqa: E402
from app.mcp_tools.company_research_tool import company_research  # noqa: E402
from app.mcp_tools.crm_lookup_tool import crm_lookup  # noqa: E402
from app.mcp_tools.lead_score_tool import lead_score  # noqa: E402
from app.mcp_tools.outreach_tool import generate_outreach  # noqa: E402
from app.mcp_tools.website_analysis_tool import website_analysis  # noqa: E402
from app.utils.logger import get_logger  # noqa: E402

log = get_logger("mcp_server")

mcp = FastMCP(
    name="leadpilot",
    instructions=(
        "LeadPilot AI — lead research, qualification, and outreach tools for sales teams. "
        "CRM lookup is read-only. Draft emails are never sent automatically; use "
        "approve_draft_email only after a human reviews the draft."
    ),
)


def _json(result: dict) -> str:
    """MCP tools return JSON strings so all clients get a consistent shape."""
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool(
    name="crm_lookup",
    description=(
        "Look up leads in the CRM by lead ID (e.g. L-001), person name, company name, "
        "or pass 'all' to list every lead. Read-only — does not modify CRM data."
    ),
)
def mcp_crm_lookup(query: str) -> str:
    return _json(crm_lookup(query))


@mcp.tool(
    name="company_research",
    description=(
        "Search the web for company overview, recent news, growth signals, and tech stack. "
        "Uses cache and mock mode when MOCK_MODE=TRUE (zero API cost during development)."
    ),
)
def mcp_company_research(company_name: str, industry: str) -> str:
    return _json(company_research(company_name, industry))


@mcp.tool(
    name="website_analysis",
    description=(
        "Scrape and analyze a company website for title, description, headings, and tech hints. "
        "Results are cached for 24 hours."
    ),
)
def mcp_website_analysis(url: str) -> str:
    return _json(website_analysis(url))


@mcp.tool(
    name="lead_score",
    description=(
        "Calculate a deterministic lead score (0-100) and Hot/Warm/Cold tier from CRM + research data. "
        "Each of five factors scores 0-20. Hot >= 75, Warm >= 55, Cold < 55."
    ),
)
def mcp_lead_score(
    industry: str,
    company_size: str,
    title: str,
    notes: str,
    growth_signal_count: int,
    source_count: int,
    tech_stack_count: int,
    has_website: str,
) -> str:
    return _json(
        lead_score(
            industry=industry,
            company_size=company_size,
            title=title,
            notes=notes,
            growth_signal_count=growth_signal_count,
            source_count=source_count,
            tech_stack_count=tech_stack_count,
            has_website=has_website,
        )
    )


@mcp.tool(
    name="generate_outreach",
    description=(
        "Generate recommendation, talking points, draft email, timeline, and report for a qualified lead. "
        "Does NOT send email — draft status is always pending_approval until a human approves. "
        "Pass lead_id (e.g. L-001) so approve_draft_email can find the draft later."
    ),
)
def mcp_generate_outreach(
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
    lead_id: str,
) -> str:
    from app.mcp_server.approval_store import register_draft

    result = generate_outreach(
        lead_name=lead_name,
        company=company,
        title=title,
        industry=industry,
        tier=tier,
        score=score,
        notes=notes,
        reasoning=reasoning,
        recent_news=recent_news,
        growth_signals=growth_signals,
    )
    if lead_id.strip():
        register_draft(lead_id.strip(), result.get("draft_email"))
    return _json(result)


@mcp.tool(
    name="approve_draft_email",
    description=(
        "Human-in-the-loop gate: approve or reject a draft email for a lead. "
        "Does not actually send mail — records the human decision only. "
        "action must be 'approve' or 'reject'."
    ),
)
def mcp_approve_draft_email(lead_id: str, action: str) -> str:
    return _json(approve_draft_email(lead_id, action))


def run_stdio() -> None:
    """Start the MCP server on stdio (default for Cursor / Claude Desktop)."""
    log.info("LeadPilot MCP server starting (stdio)")
    mcp.run(transport="stdio")
