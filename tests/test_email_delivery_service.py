"""Email delivery service tests (no live Gmail calls)."""

import pytest

from app.services.email_delivery_service import (
    EmailDeliveryConfigError,
    _build_demo_email,
    _prepare_draft_body,
    send_approved_email,
)
from config import settings


def test_build_demo_email_uses_demo_recipient() -> None:
    old_to = settings.gmail_demo_to_email
    try:
        settings.gmail_demo_to_email = "demo@example.com"
        msg = _build_demo_email(
            "L-001",
            {"company": "Stripe", "industry": "Fintech"},
            {"subject": "Intro", "body": "Hello there\n\nBest,\n[Your name]"},
        )
        assert msg["To"] == "demo@example.com"
        assert msg["Subject"] == "Intro"
        body = msg.get_content()
        assert "Lead ID:" not in body
        assert "--- Original Draft ---" not in body
        assert "[Your name]" not in body
        assert "Stripe" in body
    finally:
        settings.gmail_demo_to_email = old_to


def test_prepare_draft_body_replaces_signature_placeholder_case_insensitive() -> None:
    body = "Hi there,\n\nThanks.\n\nBest,\n[your name]"
    out = _prepare_draft_body(body, "HubSpot")
    assert "[your name]" not in out
    assert out.endswith("HubSpot")


def test_send_approved_email_simulates_in_mock_mode() -> None:
    old_mode = settings.mock_mode
    old_to = settings.gmail_demo_to_email
    try:
        settings.mock_mode = True
        settings.gmail_demo_to_email = "demo@example.com"
        result = send_approved_email(
            "L-001",
            {"company": "Stripe"},
            {"subject": "Hello", "body": "Body"},
        )
        assert result["provider"] == "mock"
        assert result["to"] == "demo@example.com"
    finally:
        settings.mock_mode = old_mode
        settings.gmail_demo_to_email = old_to


def test_send_approved_email_requires_enabled_flag() -> None:
    old_mode = settings.mock_mode
    old_enabled = settings.gmail_send_enabled
    old_to = settings.gmail_demo_to_email
    try:
        settings.mock_mode = False
        settings.gmail_send_enabled = False
        settings.gmail_demo_to_email = "demo@example.com"
        with pytest.raises(EmailDeliveryConfigError):
            send_approved_email(
                "L-001",
                {"company": "Stripe"},
                {"subject": "Hello", "body": "Body"},
            )
    finally:
        settings.mock_mode = old_mode
        settings.gmail_send_enabled = old_enabled
        settings.gmail_demo_to_email = old_to

