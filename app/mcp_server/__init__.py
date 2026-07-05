"""LeadPilot MCP server — exposes CRM, research, scoring, and outreach tools."""

from app.mcp_server.server import mcp, run_stdio

__all__ = ["mcp", "run_stdio"]
