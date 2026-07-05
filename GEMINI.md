# GEMINI.md — Project Context for AI Assistants

## What this project is

**Lead Qualification AI** — a multi-agent system built on Google ADK (Python) that researches, qualifies, scores, and prioritizes sales leads. Capstone for the Google 5-Day AI Agents Intensive 2026, "Agents for Business" track.

## Rules of engagement

1. **Read [MASTER.md](MASTER.md) before writing any code.** It defines the architecture, the API-budget rules, security rules, and code practices. Those rules override any default you would otherwise apply.
2. **Follow the build order** in MASTER.md section 1. Do not start a later phase early; do not add agents, tools, or abstractions beyond the current phase.
3. **Never burn API credits.** `MOCK_MODE=TRUE` is the default. Every external tool must go through the disk cache (`app/utils/cache.py`) and the budget guard (`app/utils/api_budget.py`). Development and tests must work fully offline.
4. **Never touch secrets.** `.env` is git-ignored and must stay that way. Config is read only via `config.settings`.
5. **Do not change the model** (`gemini-flash-latest` via `GEMINI_MODEL`) unless explicitly asked.

## Key commands

```bash
uv sync                                   # install dependencies
uv run pytest                             # offline test suite
uv run python main.py "prompt here"       # one-shot CLI run
uv run uvicorn app.api.server:app --port 8100   # dashboard backend API
cd frontend; npm run dev                  # React dashboard at localhost:5173
uv run adk web . --port 8000              # raw ADK playground
uv run ruff check . --fix                 # lint
```

## Layout cheat-sheet

| Path | Contents |
|---|---|
| `app/agent.py` | ADK entry point — `root_agent` lives here |
| `app/agents/` | Specialist agents (research, qualification, outreach) |
| `app/mcp_tools/` | Tools (also exposed via MCP server in phase 4) |
| `app/skills/` | Domain playbooks (qualification rubric, scoring, outreach) |
| `app/security/` | PII redaction, injection screening, audit log |
| `app/utils/` | `logger.py`, `cache.py`, `api_budget.py` — use these, don't reinvent |
| `app/api/` | FastAPI backend serving the React dashboard |
| `frontend/` | React dashboard (Vite + Tailwind v4 + Recharts, dark theme) |
| `config.py` | Typed settings from `.env` — the ONLY place env vars are read |
| `data/` | Sample CRM (`sample_leads.csv`) + mock pipeline results (`mock_data.json`) |
| `tests/` | pytest — deterministic code only, never LLM output assertions |
| `evaluation/` | ADK eval — the ONLY place agent behavior is validated |

## Conventions that trip people up

- Tools return dicts with a `status` key and never raise to the agent (MASTER.md C2/C3).
- Tool docstrings are the LLM-facing spec — write them for the model.
- Tool signatures: type hints required, **no default values** (ADK requirement).
- Agents pass data via session state (`output_key`), not by repeating text.
- Sub-agents are created via factory functions when composing pipelines.
- `App(name=...)` must stay `"app"` (matches the directory; mismatch breaks eval).
