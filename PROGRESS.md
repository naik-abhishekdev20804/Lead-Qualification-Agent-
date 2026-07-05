# PROGRESS.md — Build Log & Roadmap

Single source of truth for **what's built, how it works, and what's next**.
Update this file at the end of every phase. See [`MASTER.md`](MASTER.md) for
the rules this build follows, [`README.md`](README.md) for the project pitch,
and [`GEMINI.md`](GEMINI.md) for AI-assistant context.

Last updated: **Gmail real-send runtime verification + frontend/backend routing alignment**.

---

## 1. Current status at a glance

| Phase | Status | What it delivers |
|---|---|---|
| 0 — Setup & baseline agent | ✅ Done | Config, cache, budget guard, CRM tool, one working agent |
| Dashboard (React UI) | ✅ Done | Full frontend + FastAPI backend, wired to live agent + mock pipeline data |
| 1 — Research agent | ✅ Done | Tavily/Serper/Firecrawl tools, research_agent, API research endpoint |
| 1b — Live deep research | ✅ Done | Multi-query Tavily + Firecrawl v4, URL discovery, rich extraction |
| 2 — Qualification agent | ✅ Done | Scoring tool, qualification skill, qualify_pipeline, live scoring API |
| 3 — Outreach agent | ✅ Done | Recommendation, report, draft email, human approval |
| 4 — MCP server | ✅ Done | stdio MCP server exposing all tools + HITL approval gate |
| CRM data model | ✅ Done | Minimum fields, 4 real companies — intel from Tavily/Firecrawl |
| 5 — Security layer | ⬜ Next | PII redaction, prompt-injection screening, audit log |
| 6 — Evaluation | ⬜ Not started | ADK eval datasets, LLM-as-judge, tool-trajectory checks |
| 7 — Polish | ⬜ Not started | Deployment, demo recording, final docs |

**Test suite:** `77 passed` (offline, `MOCK_MODE=TRUE`).

---

## 2. What's implemented (detailed)

### 2.1 Project foundation

- **`pyproject.toml`** — `uv`-managed project. Runtime deps: `google-adk`, `python-dotenv`,
  `pydantic` / `pydantic-settings`, `httpx`, `tavily-python`, `firecrawl-py`, `mcp>=1.28.1`,
  and Gmail delivery deps (`google-api-python-client`, `google-auth-oauthlib`,
  `google-auth-httplib2`).
  Dev deps: `pytest`, `pytest-asyncio`, `ruff`.
- **`config.py`** — the *only* place environment variables are read. Typed `Settings`
  (pydantic-settings) loaded from `.env`. Exposes `settings` singleton plus `PROJECT_ROOT`,
  `DATA_DIR`, `CACHE_DIR`, `LOG_DIR`.
- **`.env` / `.env.example`** — `GOOGLE_API_KEY`, `GEMINI_MODEL=gemini-flash-latest`,
  `TAVILY_API_KEY`, `SERPER_API_KEY`, `FIRECRAWL_API_KEY`, `MOCK_MODE`, `CACHE_TTL_HOURS`,
  `DAILY_API_BUDGET`.
- **`.gitignore`** — excludes `.env`, `.cache/`, `logs/`, venvs, `node_modules/`, build output.

### 2.2 API-budget protection

- **`app/utils/cache.py`** — SHA-256-keyed JSON disk cache under `.cache/`. 24h TTL by default.
- **`app/utils/api_budget.py`** — daily per-provider call counter (default cap 50/provider).
- **`MOCK_MODE=TRUE`** (default) — external tools return stubs with zero network calls.
- Live mode: cache → budget guard → Tavily/Serper/Firecrawl, never crash the agent run.

### 2.3 Logging

- **`app/utils/logger.py`** — namespaced loggers to console + `logs/app.log`.

### 2.4 CRM — minimum data model (demo showcase)

**Design rule:** CRM stores the *minimum* input; **Tavily + Firecrawl fetch all detailed intel**.

- **`data/sample_leads.csv`** — **4 real companies**, 3 columns only (+ lead ID):

  | ID | Company | Industry | CRM note |
  |---|---|---|---|
  | L-001 | Stripe | Fintech | Requested enterprise pricing demo |
  | L-002 | Notion | SaaS | Downloaded whitepaper |
  | L-003 | HubSpot | SaaS | Asked about security compliance |
  | L-004 | Shopify | E-commerce | Cold inbound from contact form |

  No fake contacts, employee counts, emails, or placeholder websites.

- **`app/mcp_tools/crm_lookup_tool.py`** — read-only CSV lookup by ID, company, or notes.
  Uses `.get()` for optional fields so minimal rows work.

- **`data/mock_research.json`** — tiny offline pytest stubs only (“run Research for live data”).
  **Not** used as fake rich company profiles in production demos.

- **`data/mock_data.json`** — dashboard *preview* scores/outreach for first page load.
  Research sections say **“Click Research for Tavily + Firecrawl live intel.”**

### 2.5 Live research pipeline (Tavily + Firecrawl)

When `MOCK_MODE=FALSE` and API keys are set:

- **`app/mcp_tools/_research_extract.py`** — parses search/scrape text into overview, news,
  growth signals, tech stack, official website URL, detailed summary. No LLM.
- **`app/mcp_tools/company_research_tool.py`** — **two Tavily queries** per company:
  1. Overview — `search_depth=advanced`, `include_answer=advanced`, 8 results
  2. News — `topic=news`, `time_range=year`, 6 results  
  Falls back to Serper if Tavily returns nothing. Cached 24h.
- **`app/mcp_tools/website_analysis_tool.py`** — **Firecrawl v4** `scrape()` (legacy API fallback).
  Skips placeholder CRM URLs; Tavily discovers the real homepage first.
  Extracts tech hints from page markdown.
- **`app/services/research_service.py`** — orchestrates CRM → Tavily → URL discovery → Firecrawl.
  Returns `research_summary` with `detailed_summary`, `official_website`, `live` flag.

**Demo flow:** open lead → see company + one note → **Research only** → live intel fills UI →
**Qualify + outreach** → score/email use enriched data.

Without live research, scores stay **Cold** (by design — proves Tavily/Firecrawl value).

### 2.6 Backend agent (Google ADK)

- **`app/agent.py`** — `root_agent` orchestrator with 9 tools + 5 AgentTools:
  `crm_lookup`, `company_research`, `website_analysis`, `lead_score`, `generate_outreach`,
  research/qualification/outreach agents, `full_pipeline`, `qualify_pipeline`.
- **`create_full_pipeline()`** — SequentialAgent: research → qualification → outreach.
- Three specialist agents in `app/agents/` with `output_key` state passing.

### 2.7 Dashboard backend — `app/api/server.py`

FastAPI on port **8100**, CORS for `localhost:5173`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Status, mock mode, model, `live_research_ready`, key flags |
| GET | `/api/leads` | CRM + merged qualification summaries |
| GET | `/api/leads/{id}` | Full lead detail |
| POST | `/api/leads/{id}/research` | Deterministic research (no LLM) |
| POST | `/api/leads/{id}/qualify` | Full pipeline: research + score + outreach |
| POST | `/api/leads/{id}/outreach` | Outreach on cached qualification |
| POST | `/api/leads/{id}/email` | HITL approve/reject + optional real Gmail send on approve |
| POST | `/api/chat` | Live orchestrator agent |
| GET | `/api/budget` | API budget usage report |

**Run backend (Windows, no `uv` CLI needed):**
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.server:app --port 8100 --reload
```

### 2.8 Frontend — `frontend/` (React + Vite + Tailwind v4)

- **Leads page** — company-first table (company, industry, CRM notes, score, tier).
- **Lead detail** — company name as header; “CRM minimum data — click Research for live intel”;
  badges: **live research**, **live score**, **live outreach**;
  expandable **Full research report (Tavily + Firecrawl)** section;
  **Qualify + outreach** and **Research only** buttons.
- **Assistant** — suggested prompts updated for Stripe/HubSpot.
- Dev proxy: `/api → http://127.0.0.1:8101` (aligned to latest backend instance for Gmail-send verification).

**Run frontend:**
```powershell
cd frontend; npm run dev
```

### 2.9 Tests (77 passing, all offline)

| File | Tests | Covers |
|---|---|---|
| `test_setup.py` | 17 | Config, agents, CRM, cache, budget, MCP import |
| `test_agents.py` | 11 | Mock research stubs, research service, minimal CRM shape |
| `test_qualification.py` | 10 | Scoring math, minimal CRM scores low, enriched research raises score |
| `test_outreach.py` | 10 | Email rules, HITL, enriched research enables draft |
| `test_mcp_server.py` | 8 | MCP tool registry, JSON wrappers, approval gate |
| `test_research_extract.py` | 8 | URL discovery, tech/growth extraction, detailed summary |

`uv run pytest -v` or `python -m uv run pytest -v`

### 2.10 Documentation

- **`README.md`** — pitch, quick start, MCP server setup, live research config, CRM data model.
- **`GEMINI.md`**, **`MASTER.md`** — engineering rules and build order.

---

## 3. Architecture as it stands today

```
┌─────────────────────────────┐        ┌──────────────────────────────┐
│   React dashboard (5173)    │──/api──▶│  FastAPI backend (8100)      │
│   Dashboard / Leads /       │         │  app/api/server.py           │
│   LeadDetail / Assistant /  │         │  POST /research, /qualify    │
│   System                    │         │  POST /email (HITL)          │
└─────────────────────────────┘         │  POST /chat                  │
                                         └──────────────┬───────────────┘
                                                        │
                    ┌───────────────────────────────────┼───────────────────┐
                    ▼                                   ▼                   ▼
          data/sample_leads.csv              app/services/           app/agent.py
          (4 real cos, min fields)           research_service.py     root_agent + pipelines
                    │                                   │
                    │                          MOCK_MODE=FALSE:
                    │                          Tavily (2 queries)
                    │                               → Serper fallback
                    │                          Firecrawl v4 scrape
                    │                               → real website URL
                    ▼
          Deterministic scoring + outreach (no LLM for dashboard buttons)
          Gemini LLM only for /api/chat and ADK agent reasoning

  MCP server (stdio): python -m app.mcp_server  →  Cursor / external clients
  Protected by: cache.py + api_budget.py
```

---

## 4. What's next — Phase 5: Security Layer

**Goal:** PII redaction, prompt-injection screening, and audit logging before production demos.

**Planned deliverables:**

1. `app/security/validator.py` — sanitize untrusted input at boundaries.
2. `app/security/pii.py` — redact emails/phones before external API calls.
3. `app/security/injection.py` — screen scraped website content before agent prompts.
4. `app/security/audit.py` — append-only log of scoring and outreach decisions.
5. Wire security into research tools and MCP server.

---

## 5. Live research + minimal CRM log (✅ complete)

### Why this change

Showcase demo: CRM gives **company name + industry + one note** only. Judges see Tavily and
Firecrawl do the real work — not pre-baked fake research in JSON.

### Files changed

- **`data/sample_leads.csv`** — 4 real companies (Stripe, Notion, HubSpot, Shopify), 3 fields.
- **`data/mock_research.json`** — stripped to offline pytest stubs.
- **`data/mock_data.json`** — 4 leads, preview scores, placeholder research text.
- **`app/mcp_tools/_research_extract.py`** — NEW: parse live results, discover official URL,
  extract tech/growth signals, build `detailed_summary`.
- **`app/mcp_tools/company_research_tool.py`** — multi-query Tavily live mode.
- **`app/mcp_tools/website_analysis_tool.py`** — Firecrawl v4 + placeholder URL skip.
- **`app/services/research_service.py`** — URL discovery, merge website into overview.
- **`app/services/qualification_service.py`** — `.get()` defaults for missing CRM fields.
- **`app/api/server.py`** — `live_research_ready` on `/api/health`.
- **Frontend** — company-first UI, live research badge, full report expander.

### Enable live mode

```env
MOCK_MODE=FALSE
TAVILY_API_KEY=tvly-...
FIRECRAWL_API_KEY=fc-...
SERPER_API_KEY=...    # optional fallback
```

Restart backend → open lead → **Research only** → verify `/api/health` shows `live_research_ready: true`.

---

## 6. Phase 4 implementation log (MCP Server — ✅ complete)

### MCP server package

- **`app/mcp_server/server.py`** — FastMCP stdio server (`leadpilot`) wrapping all agent tools.
- **`app/mcp_server/approval_store.py`** — in-memory HITL gate for draft email approve/reject.
- **`app/mcp_server/__main__.py`** — entry point: `python -m app.mcp_server`.
- **`scripts/run_mcp_server.bat`** — Windows launcher for Cursor MCP config.

### Tools exposed via MCP

| Tool | Source | Notes |
|---|---|---|
| `crm_lookup` | `crm_lookup_tool.py` | Read-only CRM |
| `company_research` | `company_research_tool.py` | Cache + mock safe; live Tavily when configured |
| `website_analysis` | `website_analysis_tool.py` | Firecrawl v4 |
| `lead_score` | `lead_score_tool.py` | Deterministic math |
| `generate_outreach` | `outreach_tool.py` | Draft only, `pending_approval` |
| `approve_draft_email` | `approval_store.py` | Human gate — no send tool |

### Cursor integration

- **`.cursor/mcp.json`** — pre-configured `leadpilot` server.
- **`mcp>=1.28.1`** in `pyproject.toml`.

### Tests

- **`tests/test_mcp_server.py`** — 8 tests.

---

## 7. Phase 3 implementation log (Outreach Agent — ✅ complete)

- **`app/skills/outreach_skill.py`** — playbook, `EMAIL_OUTREACH_THRESHOLD=55`.
- **`app/mcp_tools/outreach_tool.py`** — recommendation, draft email, timeline, report.
- **`app/agents/outreach_agent.py`**, **`app/services/outreach_service.py`**.
- **`create_full_pipeline()`** = research → qualification → outreach.
- API: `POST /qualify`, `POST /outreach`; UI: **Qualify + outreach**, email approve/reject.
- **`tests/test_outreach.py`** — 10 tests.

---

## 8. Phase 2 implementation log (Qualification Agent — ✅ complete)

- **`app/skills/qualification_skill.py`** — BANT/ICP rubric.
- **`app/mcp_tools/lead_score_tool.py`** — 5 factors × 0–20, Hot ≥75, Warm ≥55, Cold <55.
- **`app/agents/qualification_agent.py`**, **`app/services/qualification_service.py`**.
- **`create_qualify_pipeline()`** = research → qualification.
- **`tests/test_qualification.py`** — 10 tests; includes enriched-research-raises-score test.

---

## 9. Phase 1 implementation log (Research Agent — ✅ complete)

- **`app/agents/research_agent.py`** — CRM + web + website tools.
- **`app/services/research_service.py`** — deterministic pipeline, no LLM.
- **`app/mcp_tools/company_research_tool.py`**, **`website_analysis_tool.py`**, **`serper_search_tool.py`**.
- **`POST /api/leads/{id}/research`** — dashboard Research button.
- **`tests/test_agents.py`**, **`tests/test_research_extract.py`**.

---

## 10. How to resume work in a new session

1. Read this file (`PROGRESS.md`), then `MASTER.md` for rules.
2. `python -m uv run pytest -v` — confirm **77 tests** pass.
3. Start backend + frontend (see §2.7 / §2.8).
4. For live demo: set `MOCK_MODE=FALSE` + Tavily/Firecrawl keys in `.env`, restart backend.
5. Pick up **Phase 5 (Security)** per §4 — do not skip ahead per `MASTER.md` build order.

### Common gotchas

- **`python -m uv run`** works; bare `uv` may not be on PATH. Use
  `.\.venv\Scripts\python.exe -m uvicorn ...` directly.
- If Research/Qualify buttons return **404**, restart backend — old process may lack new routes.
- Port **5174** is fine — Vite proxy still forwards `/api` to backend target in `frontend/vite.config.js`.

---

## 11. Real-time scoring hardening log (✅ complete)

### Why this change

Live research was already enabled, but two reliability gaps remained:

1. If Tavily credits/rate limits were exhausted, research could stop early without
   fully attempting Serper fallback.
2. With minimal CRM rows (no `website` column), qualification under-counted online
   presence even when Tavily discovered the official company site.

### What was improved

- **Provider error normalization**
  - Added **`app/utils/provider_errors.py`** to classify provider exceptions.
  - Quota/rate-limit style errors now map to `status="budget_exceeded"` with
    user-safe messages.
- **Tavily exhaustion fallback**
  - Updated **`app/mcp_tools/company_research_tool.py`**:
    - Tavily exceptions now use normalized status/messages.
    - If Tavily is exhausted/empty, flow still attempts **Serper fallback**.
    - Returns `budget_exceeded` only after fallback options are exhausted.
- **Firecrawl exhaustion handling**
  - Updated **`app/mcp_tools/website_analysis_tool.py`** to classify Firecrawl
    quota/rate-limit failures as `budget_exceeded`.
- **Serper exhaustion handling**
  - Updated **`app/mcp_tools/serper_search_tool.py`** with the same normalized
    budget/error behavior.
- **Website-aware scoring**
  - Updated **`app/services/qualification_service.py`** so scoring treats
    discovered `official_website` (from research) as valid online presence even
    when CRM has no website field.

### Tests added

- **`tests/test_provider_errors.py`** — quota/rate-limit and generic error
  classification.
- **`tests/test_qualification.py`** — discovered official website increases
  online-presence scoring as expected.

### Validation

- `python -m uv run pytest -q` → **69 passed** (run in `MOCK_MODE=TRUE`).
- `python -m uv run ruff check .` → **All checks passed**.

---

## 12. Research format + real email send (✅ complete)

### What changed

- **Research content limits and formatting controls**
  - Added configurable caps in `config.py`:
    - `RESEARCH_OVERVIEW_MAX_CHARS`
    - `RESEARCH_NEWS_MAX_CHARS`
    - `RESEARCH_DETAILED_SUMMARY_MAX_CHARS`
    - `RESEARCH_MAX_GROWTH_SIGNALS`
    - `RESEARCH_MAX_TECH_STACK`
    - `RESEARCH_MAX_SOURCES`
  - Applied in `app/services/research_service.py` so dashboard cards and report stay concise.

- **Approve & send now supports real Gmail delivery**
  - Added `app/services/email_delivery_service.py`.
  - `POST /api/leads/{id}/email` now:
    - on `approve`: sends via Gmail API (live mode), then marks `approved_and_sent`
    - on `reject`: marks `rejected`
  - Delivery metadata is stored with draft status and returned to frontend.

- **Frontend UX update**
  - `frontend/src/pages/LeadDetail.jsx` now shows send target after approval and surfaces API errors.

- **Safety + config**
  - Real send is opt-in:
    - `GMAIL_SEND_ENABLED=TRUE`
    - `GMAIL_DEMO_TO_EMAIL=<your inbox>`
  - Demo routing sends approved emails to your configured demo inbox, not real company contacts.

- **Gmail setup helper**
  - Added `scripts/setup_gmail_token.py` to create OAuth token from client credentials JSON.
  - Added new env vars in `.env.example` and docs in `README.md`.

- **Cache behavior fix**
  - Company/web cache is now mode-aware:
    - mock mode ignores stale live cache
    - live mode ignores stale mock cache

### Validation

- `python -m uv run pytest -q` → **77 passed**
- `python -m uv run ruff check .` → **All checks passed**

---

## 13. Gmail send rollout & runtime debug log (✅ complete)

### Why this follow-up was needed

After initial Gmail integration, UI still showed `approved_and_sent` without inbox delivery.
Root cause: frontend traffic was hitting an older backend process that still had legacy
"status-only" approval behavior.

### What was done end-to-end

1. **Verified Gmail credentials/token pipeline**
   - User generated OAuth token with `python scripts/setup_gmail_token.py`.
   - Confirmed token path `secrets/gmail_token.json` exists.
2. **Validated runtime env from `.env`**
   - `MOCK_MODE=FALSE`
   - `GMAIL_SEND_ENABLED=TRUE`
   - `GMAIL_DEMO_TO_EMAIL` set
3. **Live API verification on latest backend**
   - Started latest backend on `8101`.
   - Confirmed `/api/health` includes:
     - `gmail_send_enabled`
     - `gmail_demo_to_email_configured`
   - Confirmed `POST /api/leads/{id}/email` (approve) returns real delivery metadata:
     - provider `gmail`
     - `message_id`
     - recipient email
4. **Frontend routing alignment**
   - Updated `frontend/vite.config.js` proxy target to `http://127.0.0.1:8101`
     so UI approval flow hits the verified Gmail-enabled backend.
5. **Operational behavior clarified**
   - Draft can be approved once; to send again, rerun **Qualify + outreach** to
     regenerate `pending_approval` draft.

### Runtime checks that now pass

- `http://localhost:5173/api/health` returns Gmail flags from latest backend.
- Approve endpoint on latest backend performs real Gmail send (not just status update).
- UI can still show `Approved & sent`, now backed by real provider delivery metadata.
