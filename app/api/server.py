"""FastAPI backend for the Lead Qualification dashboard.

Run:  uv run uvicorn app.api.server:app --port 8100 --reload

Endpoints:
    GET  /api/health                     app status, mock mode, model
    GET  /api/leads                      CRM leads merged with qualification summaries
    GET  /api/leads/{lead_id}            full lead detail (research, score, email, timeline)
    POST /api/leads/{lead_id}/qualify    full pipeline: research + score + outreach (no LLM)
    POST /api/leads/{lead_id}/outreach   outreach only (uses cached qualification if available)
    POST /api/leads/{lead_id}/research   research only (no LLM)
    POST /api/leads/{lead_id}/email      approve / reject the draft email (human-in-the-loop)
    POST /api/chat                       talk to the live orchestrator agent
    GET  /api/budget                     API budget usage report

While MOCK_MODE=TRUE, qualification data comes from data/mock_data.json
(zero external API calls). The chat endpoint always uses the real agent.
"""

import json
import uuid

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app.agent import root_agent  # noqa: E402
from app.mcp_tools.crm_lookup_tool import crm_lookup  # noqa: E402
from app.services.email_delivery_service import (  # noqa: E402
    EmailDeliveryConfigError,
    EmailDeliveryError,
    send_approved_email,
)
from app.services.outreach_service import run_lead_outreach  # noqa: E402
from app.services.research_service import run_lead_research  # noqa: E402
from app.utils import api_budget  # noqa: E402
from app.utils.logger import get_logger  # noqa: E402
from config import DATA_DIR, settings  # noqa: E402

log = get_logger("api")

app = FastAPI(title="Lead Qualification AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mock qualification store (in-memory copy so email approvals persist per run) ---

_MOCK_FILE = DATA_DIR / "mock_data.json"
_qualifications: dict = json.loads(_MOCK_FILE.read_text(encoding="utf-8"))["qualifications"]

# Live research + qualification keyed by lead_id (survives until restart)
_live_research: dict[str, dict] = {}
_live_qualifications: dict[str, dict] = {}
_auto_qualified_once: set[str] = set()


def _merged_qualification(lead_id: str) -> dict | None:
    """Return qualification payload for the current runtime mode.

    - MOCK_MODE=TRUE: serve mock qualifications, optionally blended with live
      research/qualification generated during this process run.
    - MOCK_MODE=FALSE: never serve preloaded mock qualifications.
    """
    mock = _qualifications.get(lead_id)
    live_q = _live_qualifications.get(lead_id)

    if not settings.mock_mode:
        if live_q:
            qual = live_q.get("qualification", {})
            merged = {**qual}
            merged["qualification_live"] = True
            merged["outreach_live"] = qual.get("outreach_live", False)
            merged["mock"] = False
            return merged

        if lead_id in _live_research:
            live = _live_research[lead_id]
            return {
                "research_summary": live.get("research_summary"),
                "research_live": live.get("live", not live.get("mock", True)),
                "research_providers": live.get("providers", []),
                "mock": False,
            }

        return None

    if live_q:
        qual = live_q.get("qualification", {})
        merged = {**(mock or {}), **qual}
        merged["qualification_live"] = True
        merged["outreach_live"] = qual.get("outreach_live", False)
        merged["mock"] = live_q.get("mock", False)
        return merged

    if mock and lead_id in _live_research:
        live = _live_research[lead_id]
        return {
            **mock,
            "research_summary": live["research_summary"],
            "research_live": live.get("live", not live.get("mock", True)),
            "research_providers": live.get("providers", []),
            "mock": live.get("mock", mock.get("mock", False)),
        }

    return mock


def _ensure_live_qualification_for_list(lead_id: str) -> None:
    """Auto-run live qualification once so list view can show score/priority."""
    if settings.mock_mode or lead_id in _live_qualifications or lead_id in _auto_qualified_once:
        return

    _auto_qualified_once.add(lead_id)
    outcome = run_lead_outreach(lead_id)
    if outcome.get("status") != "success":
        log.warning("auto-qualification failed for %s: %s", lead_id, outcome.get("message"))
        return

    _live_research[lead_id] = {
        "status": "success",
        "lead_id": lead_id,
        "lead": outcome["lead"],
        "research_summary": outcome["qualification"]["research_summary"],
        "mock": outcome.get("mock", False),
    }
    _live_qualifications[lead_id] = outcome
    log.info("auto-qualification stored for %s (live mode)", lead_id)

# --- Agent chat session (one shared session service for the API process) ---

_session_service = InMemorySessionService()
_runner = Runner(agent=root_agent, app_name="app", session_service=_session_service)
_sessions: set[str] = set()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class EmailAction(BaseModel):
    action: str  # "approve" | "reject"


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mock_mode": settings.mock_mode,
        "model": settings.gemini_model,
        "environment": settings.environment,
        "live_research_ready": (
            not settings.mock_mode
            and bool(settings.tavily_api_key)
            and bool(settings.firecrawl_api_key)
        ),
        "tavily_configured": bool(settings.tavily_api_key),
        "firecrawl_configured": bool(settings.firecrawl_api_key),
        "gmail_send_enabled": settings.gmail_send_enabled,
        "gmail_demo_to_email_configured": bool(settings.gmail_demo_to_email),
    }


@app.get("/api/leads")
def list_leads():
    result = crm_lookup("all")
    leads = []
    for lead in result["leads"]:
        _ensure_live_qualification_for_list(lead["lead_id"])
        q = _merged_qualification(lead["lead_id"]) or {}
        leads.append({
            **lead,
            "score": q.get("score"),
            "tier": q.get("tier"),
            "confidence": q.get("confidence"),
            "priority": (q.get("recommendation") or {}).get("priority"),
            "email_status": (q.get("draft_email") or {}).get("status"),
            "mock": q.get("mock", False),
            "qualification_live": q.get("qualification_live", False),
        })
    return {"leads": leads, "mock_mode": settings.mock_mode}


@app.get("/api/leads/{lead_id}")
def lead_detail(lead_id: str):
    result = crm_lookup(lead_id)
    if result["status"] != "success":
        raise HTTPException(status_code=404, detail=f"Lead '{lead_id}' not found")

    qualification = _merged_qualification(lead_id)
    return {
        "lead": result["leads"][0],
        "qualification": qualification,
        "live_research": _live_research.get(lead_id),
        "live_qualification": _live_qualifications.get(lead_id),
    }


@app.post("/api/leads/{lead_id}/qualify")
def qualify_lead(lead_id: str):
    """Run full pipeline: research + qualification + outreach (no LLM)."""
    outcome = run_lead_outreach(lead_id)
    if outcome["status"] != "success":
        raise HTTPException(status_code=404, detail=outcome.get("message", "Lead not found"))

    _live_research[lead_id] = {
        "status": "success",
        "lead_id": lead_id,
        "lead": outcome["lead"],
        "research_summary": outcome["qualification"]["research_summary"],
        "mock": outcome.get("mock", False),
    }
    _live_qualifications[lead_id] = outcome
    log.info(
        "full pipeline stored for %s: %s, email=%s",
        lead_id,
        outcome["qualification"]["tier"],
        "drafted" if outcome.get("draft_email") else "none",
    )
    return outcome


@app.post("/api/leads/{lead_id}/outreach")
def outreach_lead(lead_id: str):
    """Run outreach on an already-qualified lead (or full pipeline if not yet qualified)."""
    cached = _live_qualifications.get(lead_id)
    if cached and cached.get("qualification", {}).get("qualification_live") and not cached.get("qualification", {}).get("outreach_live"):
        qual_only = {
            "status": "success",
            "lead_id": lead_id,
            "lead": cached["lead"],
            "qualification": cached["qualification"],
            "mock": cached.get("mock", False),
        }
        outcome = run_lead_outreach(lead_id, qualification_result=qual_only)
    else:
        outcome = run_lead_outreach(lead_id)

    if outcome["status"] != "success":
        raise HTTPException(status_code=404, detail=outcome.get("message", "Lead not found"))

    _live_qualifications[lead_id] = outcome
    return outcome


@app.post("/api/leads/{lead_id}/research")
def research_lead(lead_id: str):
    """Run deterministic research (CRM + web + website) without an LLM call."""
    outcome = run_lead_research(lead_id)
    if outcome["status"] == "not_found":
        raise HTTPException(status_code=404, detail=outcome.get("message", "Lead not found"))
    _live_research[lead_id] = outcome
    log.info("live research stored for %s", lead_id)
    return outcome


@app.post("/api/leads/{lead_id}/email")
def email_action(lead_id: str, body: EmailAction):
    """Human-in-the-loop: approve or reject a draft email."""
    merged = _merged_qualification(lead_id)
    if not merged or not merged.get("draft_email"):
        raise HTTPException(status_code=404, detail="No draft email for this lead")
    if not settings.mock_mode and merged.get("preview") and lead_id not in _live_qualifications:
        raise HTTPException(
            status_code=400,
            detail="Run Qualify + outreach first to generate a live draft email.",
        )
    if body.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    delivery: dict | None = None
    if body.action == "approve":
        lead_data = merged.get("lead") or crm_lookup(lead_id).get("leads", [{}])[0]
        draft_email = merged.get("draft_email") or {}
        try:
            delivery = send_approved_email(lead_id, lead_data, draft_email)
        except EmailDeliveryConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EmailDeliveryError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        new_status = "approved_and_sent"
    else:
        new_status = "rejected"

    if lead_id in _live_qualifications:
        _live_qualifications[lead_id]["qualification"]["draft_email"]["status"] = new_status
        if delivery:
            _live_qualifications[lead_id]["qualification"]["draft_email"]["delivery"] = delivery
        if _live_qualifications[lead_id].get("draft_email"):
            _live_qualifications[lead_id]["draft_email"]["status"] = new_status
            if delivery:
                _live_qualifications[lead_id]["draft_email"]["delivery"] = delivery
    elif (
        settings.mock_mode
        and lead_id in _qualifications
        and _qualifications[lead_id].get("draft_email")
    ):
        _qualifications[lead_id]["draft_email"]["status"] = new_status
        if delivery:
            _qualifications[lead_id]["draft_email"]["delivery"] = delivery
    else:
        raise HTTPException(status_code=404, detail="No draft email for this lead")

    log.info("email %s for lead %s (human decision)", new_status, lead_id)
    response = {"lead_id": lead_id, "email_status": new_status}
    if delivery:
        response["delivery"] = delivery
    return response


@app.post("/api/chat")
async def chat(body: ChatRequest):
    session_id = body.session_id or f"web-{uuid.uuid4().hex[:8]}"
    if session_id not in _sessions:
        await _session_service.create_session(
            app_name="app", user_id="web_user", session_id=session_id
        )
        _sessions.add(session_id)

    reply = ""
    tool_calls: list[str] = []
    async for event in _runner.run_async(
        user_id="web_user",
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=body.message)]),
    ):
        calls = event.get_function_calls() if hasattr(event, "get_function_calls") else []
        for call in calls or []:
            tool_calls.append(call.name)
        if event.is_final_response() and event.content and event.content.parts:
            reply = event.content.parts[0].text or ""

    return {"reply": reply, "session_id": session_id, "tool_calls": tool_calls}


@app.get("/api/budget")
def budget():
    return api_budget.usage_report()
