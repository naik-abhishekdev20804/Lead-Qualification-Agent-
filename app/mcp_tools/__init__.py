"""Tools exposed through the MCP server (Phase 4).

Implemented:
- crm_lookup_tool.py       — local CRM CSV lookup (zero API cost)
- company_research_tool.py — Tavily search with Serper fallback
- serper_search_tool.py    — internal Serper fallback (not agent-facing)
- website_analysis_tool.py — Firecrawl website scrape
- lead_score_tool.py       — deterministic scoring math (Phase 2 ✅)
- outreach_tool.py         — recommendations + draft emails (Phase 3 ✅)

Exposed via MCP server: `app/mcp_server/` (Phase 4 ✅)
"""
