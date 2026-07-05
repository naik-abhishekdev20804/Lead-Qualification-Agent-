"""ADK entry point — defines `root_agent`.

Pipeline (built phase by phase — see MASTER.md):
    Phase 1 ✅  research_agent       -> output_key="research_findings"
    Phase 2 ✅  qualification_agent  -> output_key="qualification"
    Phase 3 ✅  outreach_agent       -> output_key="final_report"

The full_pipeline SequentialAgent runs all three stages in order.
The orchestrator handles free-form chat and can delegate to specialists.
"""

from google.adk.agents import Agent, SequentialAgentfrom google.adk.tools import AgentToolfrom app.agents.outreach_agent import create_outreach_agentfrom app.agents.qualification_agent import create_qualification_agentfrom app.agents.research_agent import create_research_agentfrom app.mcp_tools.company_research_tool import company_researchfrom app.mcp_tools.crm_lookup_tool import crm_lookupfrom app.mcp_tools.lead_score_tool import lead_scorefrom app.mcp_tools.outreach_tool import generate_outreachfrom app.mcp_tools.website_analysis_tool import website_analysisfrom config import settingsdef create_full_pipeline() -> SequentialAgent:
    """Research → Qualification → Outreach sequential pipeline."""
    return SequentialAgent(
        name="full_pipeline",
        description=(
            "Complete lead qualification pipeline: researches the company, scores the lead "
            "(Hot/Warm/Cold), then generates recommendations and a draft follow-up email "
            "awaiting human approval. Use for end-to-end lead evaluation."
        ),
        sub_agents=[
            create_research_agent(),
            create_qualification_agent(),
            create_outreach_agent(),
        ],
    )


def create_qualify_pipeline() -> SequentialAgent:
    """Research → Qualification only (no outreach). Backward-compatible alias."""
    return SequentialAgent(
        name="qualify_pipeline",
        description=(
            "Research and score a lead (Hot/Warm/Cold) without generating outreach. "
            "Use when the user only wants research + scoring, not email drafting."
        ),
        sub_agents=[
            create_research_agent(),
            create_qualification_agent(),
        ],
    )


root_agent = Agent(
    name="lead_qualification_orchestrator",
    model=settings.gemini_model,
    description="Orchestrates lead qualification: research, scoring, and recommendations.",
    instruction="""You are the orchestrator of a Lead Qualification AI system for sales teams.

You help users identify, evaluate, and prioritize sales leads.

Available capabilities:
- `crm_lookup` — look up leads in the CRM by lead ID (e.g. "L-001"), person name,
  company name, or "all" to list every lead.
- `company_research` — search the web for company news, funding, growth signals.
- `website_analysis` — scrape a company's website for title, description, tech hints.
- `lead_score` — calculate a deterministic score (0-100) and Hot/Warm/Cold tier.
- `generate_outreach` — create recommendation, draft email, and report from qualification data.
- `research_agent` — specialist: full research (CRM + web + website).
- `qualification_agent` — specialist: scores a lead using the ICP/BANT rubric.
- `outreach_agent` — specialist: recommendations + draft email (human approval required).
- `full_pipeline` — research → score → outreach in one sequence. Best for "qualify this lead".
- `qualify_pipeline` — research → score only (no email drafting).

When a user asks about a lead:
1. Look the lead up in the CRM first.
2. For full evaluation with email draft, use full_pipeline.
3. For score only, use qualify_pipeline or lead_score.
4. Remind users that draft emails require human approval before sending.

Rules:
- Never invent lead data. If the CRM has no match, say so.
- Never expose personal data (emails, phones) unless the user explicitly asks.
- Never claim an email was sent — drafts always need human approval.
- Use tool numbers exactly — do not make up scores.
""",
    tools=[
        crm_lookup,
        company_research,
        website_analysis,
        lead_score,
        generate_outreach,
        AgentTool(create_research_agent()),
        AgentTool(create_qualification_agent()),
        AgentTool(create_outreach_agent()),
        AgentTool(create_full_pipeline()),
        AgentTool(create_qualify_pipeline()),
    ],
)
