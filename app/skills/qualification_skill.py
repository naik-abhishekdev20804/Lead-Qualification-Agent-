"""Qualification rubric — BANT/ICP playbook loaded by the qualification agent.

Skills are domain playbooks (instructions + constants), not executable tools.
The actual score math lives in lead_score_tool.py (MASTER.md A7).
"""

QUALIFICATION_RUBRIC = """
## Ideal Customer Profile (ICP)

Target verticals (best → acceptable):
- **Tier A (best fit):** SaaS, Fintech, Healthcare technology
- **Tier B (good fit):** Advertising/MarTech, Professional Services
- **Tier C (stretch):** Food & Beverage, Retail, Other

Ideal company size: **50–2,000 employees** (mid-market + enterprise).
Below 25 employees = typically below budget threshold.

## BANT signals to look for

| Signal | Strong | Weak |
|---|---|---|
| **Budget** | Pricing demo request, enterprise security docs | Whitepaper download only |
| **Authority** | VP, CTO, Head of, Founder | Manager, Coordinator |
| **Need** | Referral, explicit product interest | Cold contact form |
| **Timeline** | Demo scheduled, RFP, security review | Content browsing |

## Tier thresholds (deterministic — from lead_score tool)

| Tier | Score | Action |
|---|---|---|
| **Hot** | 75–100 | Contact within 24–48 hours |
| **Warm** | 55–74 | Follow up within 3 days |
| **Cold** | 0–54 | Nurture or deprioritize |

## Your job as Qualification Agent

1. Read the research findings provided in context (company overview, news, growth signals).
2. Call `lead_score` with the lead's industry, size, title, notes, and research counts.
3. Explain the score using the breakdown — never invent numbers the tool didn't return.
4. State the tier and give 2–3 sentences of sales-ready reasoning.
"""

TIER_THRESHOLDS = {
    "Hot": 75,
    "Warm": 55,
    "Cold": 0,
}

ICP_INDUSTRY_SCORES: dict[str, int] = {
    "SaaS": 18,
    "Fintech": 20,
    "Healthcare": 16,
    "Advertising": 12,
    "Food & Beverage": 6,
}

DECISION_MAKER_TITLES = ("vp", "cto", "ceo", "cfo", "coo", "founder", "head of", "director", "president")
