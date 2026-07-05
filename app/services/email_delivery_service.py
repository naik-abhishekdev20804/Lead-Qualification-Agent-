"""Gmail delivery for approved outreach drafts."""

import base64
import re
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from app.utils.logger import get_logger
from config import PROJECT_ROOT, settings

log = get_logger("email_delivery")

_GMAIL_SEND_SCOPE = ["https://www.googleapis.com/auth/gmail.send"]
_YOUR_NAME_PLACEHOLDER_RE = re.compile(r"\[\s*your\s+name\s*\]", re.I)


class EmailDeliveryConfigError(Exception):
    """Raised when Gmail delivery is not configured correctly."""


class EmailDeliveryError(Exception):
    """Raised when Gmail API call fails."""


def _resolve_project_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _trim(text: str, max_chars: int) -> str:
    clean = (text or "").strip()
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3].rstrip() + "..."


def _prepare_draft_body(draft_body: str, company_name: str) -> str:
    """Return cleaned draft body with placeholder signature replaced."""
    body = (draft_body or "").strip()
    signer = (company_name or "").strip() or "LeadPilot Team"
    if not body:
        return f"Hi there,\n\nThanks for your time.\n\nBest,\n{signer}"
    return _YOUR_NAME_PLACEHOLDER_RE.sub(signer, body)


def _build_demo_email(
    lead_id: str,
    lead: dict[str, Any],
    draft_email: dict[str, Any],
) -> EmailMessage:
    to_email = settings.gmail_demo_to_email.strip()
    if not to_email:
        raise EmailDeliveryConfigError("Set GMAIL_DEMO_TO_EMAIL in .env before approving sends.")

    base_subject = draft_email.get("subject") or f"Lead {lead_id} follow-up"
    subject = base_subject

    msg = EmailMessage()
    msg["To"] = to_email
    if settings.gmail_sender_email.strip():
        msg["From"] = settings.gmail_sender_email.strip()
    msg["Subject"] = _trim(subject, 220)

    body = _prepare_draft_body(draft_email.get("body", ""), lead.get("company", ""))
    msg.set_content(_trim(body, 20000))
    return msg


def _gmail_credentials() -> Any:
    token_path = _resolve_project_path(settings.gmail_token_file)
    if not token_path.exists():
        raise EmailDeliveryConfigError(
            f"Gmail token file missing: {token_path}. Run scripts/setup_gmail_token.py first."
        )

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except Exception as exc:  # pragma: no cover - dependency/runtime issue
        raise EmailDeliveryConfigError(
            "Gmail dependencies missing. Run `python -m uv sync` to install project deps."
        ) from exc

    creds = Credentials.from_authorized_user_file(str(token_path), _GMAIL_SEND_SCOPE)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    if not creds.valid:
        raise EmailDeliveryConfigError(
            "Gmail token is invalid/expired. Re-run scripts/setup_gmail_token.py."
        )
    return creds


def _send_via_gmail_api(msg: EmailMessage) -> dict[str, Any]:
    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except Exception as exc:  # pragma: no cover - dependency/runtime issue
        raise EmailDeliveryConfigError(
            "gmail api client not installed. Run `python -m uv sync` and retry."
        ) from exc

    creds = _gmail_credentials()
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        response = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except HttpError as exc:
        raise EmailDeliveryError(f"Gmail API error: {exc}") from exc

    return {
        "provider": "gmail",
        "message_id": response.get("id", ""),
        "thread_id": response.get("threadId", ""),
        "to": msg["To"],
    }


def send_approved_email(lead_id: str, lead: dict[str, Any], draft_email: dict[str, Any]) -> dict[str, Any]:
    """Send an approved draft email to the configured demo recipient."""
    if settings.mock_mode:
        return {
            "provider": "mock",
            "to": settings.gmail_demo_to_email.strip() or "demo-email-not-set",
            "note": "MOCK_MODE=TRUE — send simulated only.",
        }

    if not settings.gmail_send_enabled:
        raise EmailDeliveryConfigError(
            "Real email send is disabled. Set GMAIL_SEND_ENABLED=TRUE to enable Gmail delivery."
        )

    msg = _build_demo_email(lead_id, lead, draft_email)
    delivery = _send_via_gmail_api(msg)
    log.info("gmail delivery success for %s to %s", lead_id, delivery.get("to"))
    return delivery

