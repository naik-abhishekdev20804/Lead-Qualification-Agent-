"""Outreach agent — recommendations, reports, and draft emails with human approval.

Phase 3 agent. Reads qualification from session state, calls generate_outreach tool,
writes final_report to output_key.
"""

from google.adk.agents import Agent

from app.mcp_tools.outreach_tool import generate_outreach
from app.skills.outreach_skill import OUTREACH_PLAYBOOK
from config import settings


def create_outreach_agent() -> Agent:
    """Build the outreach specialist agent."""
    return Agent(
        name="outreach_agent",
        model=settings.gemini_model,
        description=(
            "Generates sales recommendations, detailed reports, and personalized draft "
            "follow-up emails for qualified leads. Never sends email — all drafts require "
            "human approval. Use after a lead has been researched and scored."
        ),
        instruction=f"""You are the Outreach Agent in a Lead Qualification system.

Your job: turn qualification results into actionable sales output.

{OUTREACH_PLAYBOOK}

Workflow:
1. Read the qualification results in context (score, tier, reasoning, research findings).
2. Call `generate_outreach` with the lead's name, company, title, industry, tier, score,
   notes, reasoning, recent_news, and comma-separated growth_signals from research.
3. Present the recommendation, talking points, and draft email (if any) clearly.
4. Remind the user that the email is a DRAFT — it will not be sent until a human approves it.
5. If tier is Cold, explain why no email was drafted and what nurture action to take.

Rules:
- Never send or pretend to send an email.
- Use the tool's output exactly — do not rewrite the draft unless asked.
- Always show the recommended action and priority.
""",
        tools=[generate_outreach],
        output_key="final_report",
    )
