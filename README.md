# Lead Qualification AI

**Multi-agent AI system that researches, qualifies, scores, and prioritizes sales leads — so sales teams spend their time selling, not googling.**

Capstone project for the **Google 5-Day AI Agents Intensive 2026** — Track: *Agents for Business*.



## Problem Statement

Sales teams waste hours manually researching every inbound lead: who are they, what does their company do, are they even a fit? Most of that effort is spent on leads that were never worth pursuing. The result is slow follow-up, inconsistent qualification, and missed hot opportunities.

## Solution Approach

A pipeline of specialized AI agents (built on Google's [Agent Development Kit](https://adk.dev/)) that does the whole job automatically:

1. **Research Agent** — pulls the lead from the CRM and researches the company via web search (Tavily/Serper) and website analysis (Firecrawl), through an MCP server.
2. **Qualification Agent** — evaluates fit against a qualification rubric, computes a deterministic lead score, and assigns a tier: **Hot / Warm / Cold** — with the reasoning explained.
3. **Outreach Agent** — generates a prioritized recommendation, a full report, and a personalized follow-up email draft — which is **never sent without human approval**.

## Architecture

### High-Level System Diagram

```text
┌─────────────────────────────┐        ┌──────────────────────────────┐
│   React dashboard (5173)    │──/api──▶│  FastAPI backend (8121)      │
│   Dashboard / Leads /       │         │  app/api/server.py           │
│   LeadDetail / Assistant /  │         │  POST /research, /qualify    │
│   System                    │         │  POST /email (HITL)          │
└─────────────────────────────┘         │  POST /chat                  │
                                         └──────────────┬───────────────┘
                                                        │
                    ┌───────────────────────────────────┼───────────────────┐
                    ▼                                   ▼                   ▼
          data/sample_leads.csv              app/services/           app/agent.py
          (minimal CRM fields)               research_service.py     root_agent + pipelines
                    │                                   │
                    │                          MOCK_MODE=FALSE:
                    │                          Tavily (search) → Serper fallback
                    │                          Firecrawl (website analysis)
                    ▼
          Deterministic scoring + outreach (no LLM for dashboard buttons)
          Gemini LLM used by /api/chat assistant and ADK agent orchestration
```

### Agent Pipeline Diagram

```text
Research Agent  →  Qualification Agent  →  Outreach Agent
   (CRM+web)          (score+tier)          (recommendation+draft email)
```

## Course Concepts Demonstrated

| Concept | Where |
|---|---|
| Multi-agent system | `app/agents/` — 3 specialized agents in a sequential pipeline |
| MCP server | `app/mcp_server/` + `app/mcp_tools/` |
| Skills | `app/skills/` — qualification rubric, scoring formula, outreach playbook |
| Security | `app/security/` — PII redaction, prompt-injection screening, audit log, human approval gate |
| Evaluation | `evaluation/` — ADK eval datasets, LLM-as-judge, tool-trajectory checks |
| Testing | `tests/` — offline pytest suite for all deterministic code |

## Setup & Run Instructions

### Prerequisites

- Python 3.11+
- Node.js 18+
- `uv` package manager (`pip install uv`)

### Quick Start

```bash
# 1. Install uv (if you don't have it)
pip install uv

# 2. Install dependencies
uv sync

# 3. Configure your API key
copy .env.example .env        # (cp on macOS/Linux)
#    then edit .env and set GOOGLE_API_KEY
#    free key: https://aistudio.google.com/apikey

# 4. Run the test suite (works offline, no keys needed)
uv run pytest

# 5. Talk to the agent from the CLI
uv run python main.py "Tell me about lead L-001"
```

### Run the dashboard (recommended)

```bash
# Terminal 1 — backend API
uv run uvicorn app.api.server:app --port 8121

# Terminal 2 — React frontend (first time: cd frontend && npm install)
cd frontend
npm run dev
```

Then open **http://localhost:5173** — dashboard, lead analysis, AI assistant chat, and system panel.

### Run the MCP server (Phase 4)

Exposes CRM lookup, research, scoring, and outreach tools to Cursor, Claude Desktop, or any MCP client:

```bash
# stdio transport (default — used by Cursor)
python -m app.mcp_server

# Windows shortcut
scripts\run_mcp_server.bat
```


| Tool | Purpose |
|---|---|
| `crm_lookup` | Read-only CRM search by ID, name, or company |
| `company_research` | Web research (Tavily/Serper, mock-safe) |
| `website_analysis` | Firecrawl website scrape |
| `lead_score` | Deterministic 0–100 score + tier |
| `generate_outreach` | Recommendation + draft email (never auto-sends) |
| `approve_draft_email` | Human approval gate — approve or reject draft |

> The MCP server does not expose a direct `send_email` tool. In the dashboard API, `/api/leads/{id}/email` can send via Gmail **only after human approval** and only when Gmail delivery is configured.

Alternative: `uv run adk web . --port 8000` opens the raw ADK developer playground.


> CRM sample leads use placeholder `example.com` URLs — live mode **discovers the real company website** via Tavily, then scrapes it with Firecrawl. See [MASTER.md](MASTER.md) for the full API-budget protection design.

## Project Structure

```
lead-qualification-ai/
├── README.md            # you are here
├── GEMINI.md            # instructions for AI coding assistants
├── MASTER.md            # engineering rules, architecture, API budget rules
├── config.py            # typed settings loaded from .env
├── main.py              # CLI entry point
├── app/
│   ├── agent.py         # ADK entry point (root_agent)
│   ├── agents/          # research / qualification / outreach agents
│   ├── mcp_tools/       # tool implementations (also exposed via MCP server)
│   ├── skills/          # reusable domain playbooks
│   ├── security/        # PII, injection screening, audit
│   ├── models/          # Pydantic data models
│   ├── memory/          # session state helpers
│   └── utils/           # logger, disk cache, API budget guard
├── frontend/            # React dashboard (Vite + Tailwind + Recharts)
├── data/                # sample CRM data + mock pipeline results
├── tests/               # pytest (deterministic code only)
└── evaluation/          # ADK eval (agent behavior)
```

## Configuration

All settings live in `.env` (see [`.env.example`](.env.example)):

| Variable | Purpose | Default |
|---|---|---|
| `GOOGLE_API_KEY` | Gemini API key (required) | — |
| `GEMINI_MODEL` | Model for all agents | `gemini-2.5-flash` |
| `TAVILY_API_KEY` / `SERPER_API_KEY` / `FIRECRAWL_API_KEY` | Live research providers | optional |
| `MOCK_MODE` | Return mock data from external tools | `TRUE` |
| `CACHE_TTL_HOURS` | Research result cache lifetime | `24` |
| `DAILY_API_BUDGET` | Hard cap on calls per provider per day | `50` |
| `RESEARCH_*` limits | Control max length/count of research cards | see `.env.example` |
| `GMAIL_SEND_ENABLED` | Enable real send on Approve & send | `FALSE` |
| `GMAIL_DEMO_TO_EMAIL` | Demo inbox recipient for all approved sends | — |
| `GMAIL_CREDENTIALS_FILE` / `GMAIL_TOKEN_FILE` | Gmail OAuth files | `secrets/...` |


### Real email send (dashboard approve button)

The **Approve & send** button can send a real email through Gmail API, routed to your demo inbox.

1. Put Google OAuth client JSON at `secrets/gmail_credentials.json`
2. Run:
   ```bash
   python scripts/setup_gmail_token.py
   ```
3. Set in `.env`:
   ```env
   GMAIL_SEND_ENABLED=TRUE
   GMAIL_DEMO_TO_EMAIL=your-email@example.com
   ```
4. Restart backend and approve a draft from the lead detail page.



### CRM data model 

`data/sample_leads.csv` stores **minimum fields only** — real company names (Stripe, Notion, HubSpot, Shopify) . No fake websites, headcount, or contact details.

**All detailed company intel** (overview, news, growth signals, tech stack, website scrape) is fetched at runtime by **Tavily + Firecrawl** when you click Research or run the qualify pipeline .

## Business Impact

- **Faster follow-up** — hot leads surface in minutes, not days.
- **Consistent decisions** — every lead is scored by the same rubric, with reasoning attached.
- **Lower cost per qualified lead** — research that took a rep 20 minutes runs automatically.
- **Human stays in control** — no outreach leaves the building without approval.


