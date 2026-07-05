"""In-memory draft email approval store for the MCP server (human-in-the-loop gate).

Separate from the FastAPI server's live store — MCP clients track approvals
via this module. No email is ever sent; approve only records the decision.
"""

from app.utils.logger import get_logger

log = get_logger("mcp_approval")

# lead_id -> {subject, body, status}
_drafts: dict[str, dict] = {}


def register_draft(lead_id: str, draft_email: dict | None) -> None:
    """Cache a draft from generate_outreach so approve_draft_email can find it."""
    if draft_email:
        _drafts[lead_id] = {**draft_email, "status": "pending_approval"}


def approve_draft_email(lead_id: str, action: str) -> dict:
    """Record human approval or rejection of a draft email."""
    action = action.strip().lower()
    if action not in ("approve", "reject"):
        return {
            "status": "error",
            "message": "action must be 'approve' or 'reject'",
            "lead_id": lead_id,
        }

    draft = _drafts.get(lead_id)
    if not draft:
        return {
            "status": "not_found",
            "message": f"No pending draft for lead '{lead_id}'. Run generate_outreach first.",
            "lead_id": lead_id,
        }

    new_status = "approved_and_sent" if action == "approve" else "rejected"
    draft["status"] = new_status
    log.info("MCP email %s for %s (human decision)", new_status, lead_id)

    return {
        "status": "success",
        "lead_id": lead_id,
        "email_status": new_status,
        "subject": draft.get("subject"),
        "note": "Simulated send — no email was actually dispatched (HITL gate).",
    }
