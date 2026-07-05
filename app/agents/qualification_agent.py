"""Qualification agent — scores leads using deterministic math + rubric reasoning.

Phase 2 agent. Reads research_findings from session state, calls lead_score tool,
writes qualification to output_key.
"""

from google.adk.agents import Agent

from app.mcp_tools.lead_score_tool import lead_score
from app.skills.qualification_skill import QUALIFICATION_RUBRIC
from config import settings


def create_qualification_agent() -> Agent:
    """Build the qualification specialist agent."""
    return Agent(
        name="qualification_agent",
        model=settings.gemini_model,
        description=(
            "Evaluates and scores sales leads. Applies the ICP/BANT rubric and "
            "computes a deterministic score (0-100) with Hot/Warm/Cold tier. "
            "Use after research is complete, or when the user asks to score/qualify a lead."
        ),
        instruction=f"""You are the Qualification Agent in a Lead Qualification system.

Your job: evaluate whether a lead is worth pursuing and assign a score + tier.

{QUALIFICATION_RUBRIC}

Workflow:
1. Read the research findings in context (from the research agent's output).
   If no research is available, ask for the lead's industry, size, title, and CRM notes.
2. Call `lead_score` with:
   - industry, company_size, title, notes from CRM/research
   - growth_signal_count = number of growth signals in research
   - source_count = number of sources in research
   - tech_stack_count = number of tech stack items found
   - has_website = "true" if a website URL was analyzed
3. Present the score, tier, breakdown, and explain WHY using the rubric.
   Use the tool's numbers exactly — never invent scores.

Output format:
- **Score:** X/100
- **Tier:** Hot / Warm / Cold
- **Breakdown:** list each factor and its score
- **Reasoning:** 2-4 sentences a sales rep can act on immediately
""",
        tools=[lead_score],
        output_key="qualification",
    )
