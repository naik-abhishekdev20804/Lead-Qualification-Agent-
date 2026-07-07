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

import asyncio
import json
import re
import random
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
    """Preload live score once for list view without pre-generating outreach email."""
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

    # Keep score/tier preloaded for list sorting, but require explicit user action
    # (Qualify + outreach) before showing a generated draft email.
    preloaded_qualification = {**outcome["qualification"]}
    preloaded_qualification["outreach_live"] = False
    preloaded_qualification["draft_email"] = None
    preloaded_qualification["final_report"] = None

    timeline = list(preloaded_qualification.get("timeline") or [])
    if timeline:
        timeline[-1] = {
            **timeline[-1],
            "action": "Run Qualify + outreach to generate draft email",
            "status": "pending",
            "duration_ms": 0,
        }
    preloaded_qualification["timeline"] = timeline

    _live_qualifications[lead_id] = {
        **outcome,
        "qualification": preloaded_qualification,
        "draft_email": None,
        "timeline": timeline,
        "final_report": None,
    }
    log.info("auto-qualification preloaded for %s (live mode, no draft)", lead_id)


def _is_llm_quota_error(exc: Exception) -> bool:
    """Detect Gemini quota/rate-limit failures surfaced by ADK."""
    text = str(exc).lower()
    hints = (
        "resource_exhausted",
        "quota",
        "rate limit",
        "429",
        "exceeded your current quota",
    )
    return any(hint in text for hint in hints)


def _is_llm_transient_error(exc: Exception) -> bool:
    """Detect temporary Gemini backend failures (e.g., 503 high demand)."""
    text = str(exc).lower()
    hints = (
        "503",
        "unavailable",
        "high demand",
        "overloaded",
        "please try again later",
    )
    return any(hint in text for hint in hints)


def _prefer_deterministic_chat(message: str) -> bool:
    """Route common CRM/lead analysis asks to deterministic path first."""
    text = (message or "").lower()
    if "most promising" in text or "best lead" in text or "highest score" in text:
        return True
    if "list all leads" in text or ("list" in text and "lead" in text):
        return True
    if re.search(r"\bl-\d{3}\b", text):
        return True
    return False


def _deterministic_chat_fallback(message: str) -> str | None:
    """Answer common assistant prompts without an LLM call."""
    text = (message or "").lower()
    crm = crm_lookup("all")
    leads = crm.get("leads", []) if crm.get("status") == "success" else []
    if not leads:
        return "I could not load leads from CRM right now."

    if "most promising" in text or "best lead" in text or "highest score" in text:
        if not settings.mock_mode:
            for lead in leads:
                _ensure_live_qualification_for_list(lead["lead_id"])
        ranked: list[tuple[int, dict, dict]] = []
        for lead in leads:
            q = _merged_qualification(lead["lead_id"]) or {}
            if q.get("score") is not None:
                ranked.append((int(q["score"]), lead, q))

        if not ranked:
            return (
                "I cannot rank leads yet because no live qualification scores are available. "
                "Run 'Qualify + outreach' on leads first."
            )

        ranked.sort(key=lambda item: item[0], reverse=True)
        top_score, top_lead, top_q = ranked[0]
        reason = top_q.get("reasoning") or "It has the strongest score and intent signals."
        priority = (top_q.get("recommendation") or {}).get("priority", "—")
        return (
            f"Top lead right now is {top_lead.get('company', top_lead.get('lead_id'))} "
            f"({top_lead['lead_id']}) with score {top_score} ({top_q.get('tier', 'N/A')}) "
            f"and priority #{priority}.\nReason: {reason}"
        )

    if "list all leads" in text or ("list" in text and "lead" in text):
        lines = ["Here are the leads in CRM:"]
        for lead in leads:
            q = _merged_qualification(lead["lead_id"]) or {}
            if q.get("score") is not None and q.get("tier"):
                score_text = f"{q['score']} ({q['tier']})"
            else:
                score_text = "not qualified yet"
            lines.append(
                f"- {lead['lead_id']} - {lead.get('company', 'Unknown')} "
                f"({lead.get('industry', 'Unknown')}) - score: {score_text}"
            )
        return "\n".join(lines)

    lead_id_match = re.search(r"\bL-\d{3}\b", message or "", flags=re.IGNORECASE)
    if lead_id_match:
        lead_id = lead_id_match.group(0).upper()
        lookup = crm_lookup(lead_id)
        if lookup.get("status") == "success" and lookup.get("leads"):
            lead = lookup["leads"][0]
            q = _merged_qualification(lead_id) or {}
            if q.get("score") is not None and q.get("tier"):
                score_line = f"Score: {q['score']} ({q['tier']})"
            else:
                score_line = "Score not available yet (run Qualify + outreach)."
            return (
                f"{lead_id} - {lead.get('company', 'Unknown')} ({lead.get('industry', 'Unknown')})\n"
                f"CRM note: {lead.get('notes', 'N/A')}\n"
                f"{score_line}"
            )

    return None


def _demo_mock_chat_reply(message: str) -> str | None:
    """Demo-safe canned assistant replies for common showcased prompts."""
    text = (message or "").strip().lower()
    normalized = re.sub(r"\s+", " ", text)

    if normalized == "which lead looks most promising and why?":
        return (
            "HubSpot (L-003) is the most promising lead for this demo.\n\n"
            "- Score: 79 (Hot)\n"
            "- Why: strongest enterprise/security intent plus solid research signals.\n"
            "- Next step: open HubSpot and click Qualify + outreach to view the draft email."
        )

    if normalized == "tell me about lead l-001 (stripe)":
        return (
            "Stripe (L-001) is currently a Warm lead in this demo.\n\n"
            "- Strong company fit (Fintech).\n"
            "- Engagement is moderate compared with HubSpot.\n"
            "- Recommended action: follow up soon with value-first positioning."
        )

    if normalized == "list all leads in the crm":
        return (
            "Current demo lead list:\n\n"
            "- L-001: Stripe - Warm\n"
            "- L-002: Notion - Warm\n"
            "- L-003: HubSpot - Hot\n"
            "- L-004: Shopify - Cold"
        )

    if normalized == "compare stripe and hubspot as opportunities":
        return (
            "Demo comparison (Stripe vs HubSpot):\n\n"
            "- HubSpot: Hot (higher urgency and stronger enterprise/security intent)\n"
            "- Stripe: Warm (good fit, but lower immediate urgency)\n\n"
            "Priority for this demo: HubSpot first, Stripe second."
        )

    if "which one of these use ai" in normalized:
        return (
            "In this demo set, the strongest AI-usage signals are for HubSpot and Notion.\n\n"
            "- HubSpot: AI-assisted marketing and sales workflows\n"
            "- Notion: built-in AI writing/productivity features\n"
            "- Stripe/Shopify: strong automation usage, but less explicit AI signal in this summary."
        )

    return None

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
    demo_reply = _demo_mock_chat_reply(body.message)
    if demo_reply:
        # Intentional small delay for realistic demo chat behavior.
        await asyncio.sleep(2.0 + random.random())
        return {"reply": demo_reply, "session_id": session_id, "tool_calls": []}

    deterministic = _deterministic_chat_fallback(body.message)
    if deterministic and _prefer_deterministic_chat(body.message):
        return {
            "reply": (
                f"{deterministic}\n\n"
                "(Responded in deterministic mode for this CRM/lead query.)"
            ),
            "session_id": session_id,
            "tool_calls": [],
        }

    try:
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
    except Exception as exc:  # pragma: no cover - surfaced in runtime diagnostics
        if _is_llm_quota_error(exc) or _is_llm_transient_error(exc):
            reason_label = "LLM service is temporarily unavailable"
            log.warning("chat fallback activated: %s", reason_label)
            if deterministic:
                return {
                    "reply": (
                        f"{deterministic}\n\n"
                        f"(Responded in deterministic fallback mode because {reason_label}.)"
                    ),
                    "session_id": session_id,
                    "tool_calls": [],
                }
            return {
                "reply": (
                    "Assistant is temporarily unavailable because Gemini cannot serve this request right now. "
                    "This can happen due to temporary model high demand. "
                    "Please retry shortly; if it persists, update `GOOGLE_API_KEY` in `.env` and restart backend."
                ),
                "session_id": session_id,
                "tool_calls": [],
            }

        log.exception("chat endpoint failed")
        raise HTTPException(status_code=500, detail="Chat failed due to a server error.") from exc


@app.get("/api/budget")
def budget():
    return api_budget.usage_report()
