"""Research agent — gathers company intel from CRM, web search, and website scrape.

Phase 1 agent. Writes synthesized findings to session state via output_key.
Uses factory function to avoid ADK 'agent already has a parent' errors.
"""

from google.adk.agents import Agent

from app.mcp_tools.company_research_tool import company_research
from app.mcp_tools.crm_lookup_tool import crm_lookup
from app.mcp_tools.website_analysis_tool import website_analysis
from config import settings


def create_research_agent() -> Agent:
    """Build the research specialist agent."""
    return Agent(
        name="research_agent",
        model=settings.gemini_model,
        description=(
            "Researches a sales lead and their company. Looks up CRM data, "
            "searches the web (Tavily/Serper), and analyzes the company website (Firecrawl). "
            "Use when the user asks to research, investigate, or gather intel on a lead or company."
        ),
        instruction="""You are the Research Agent in a Lead Qualification system.

Your job: gather factual intelligence about a lead and their company.

Workflow for every research request:
1. Use `crm_lookup` with the lead ID or company name to get CRM basics
   (name, title, company, industry, size, website, engagement notes).
2. Use `company_research` with the company name and industry from the CRM.
3. Use `website_analysis` with the company's website URL from the CRM.
4. Synthesize everything into a structured research report with these sections:
   - **Company overview** — what they do, size, location
   - **Recent news** — funding, product launches, expansions
   - **Growth signals** — hiring, funding, M&A, new initiatives
   - **Tech stack** — tools/platforms mentioned (merge web + website hints)
   - **Engagement context** — what the lead did (from CRM notes)
   - **Sources** — list every source URL used

Rules:
- Never invent facts. If a tool returns empty data, say "not found" for that field.
- Never expose lead email/phone unless explicitly asked.
- If MOCK_MODE is active, note that findings come from mock data.
- Be concise but thorough. Sales reps need actionable intel, not essays.
""",
        tools=[crm_lookup, company_research, website_analysis],
        output_key="research_findings",
    )
