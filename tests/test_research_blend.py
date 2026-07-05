"""Tests for mock+live research blending behavior."""

from app.services.research_service import _blend_mock_with_live_web


def test_blend_prefers_live_and_keeps_fallback_shape() -> None:
    warnings: list[str] = []
    web = {
        "status": "success",
        "provider": "tavily",
        "company_overview": "Live overview",
        "recent_news": "",
        "growth_signals": ["Funding round reported"],
        "tech_stack": [],
        "sources": ["https://live.example.com"],
        "search_results": [],
    }
    blended = _blend_mock_with_live_web("HubSpot", web, warnings)
    assert blended["status"] == "success"
    assert blended["provider"] == "tavily"
    assert blended["company_overview"] == "Live overview"
    assert isinstance(blended["tech_stack"], list)
    assert isinstance(blended["growth_signals"], list)
    assert not warnings


def test_blend_uses_mock_when_live_fails() -> None:
    warnings: list[str] = []
    web = {"status": "error", "provider": "tavily", "message": "quota exhausted"}
    blended = _blend_mock_with_live_web("Stripe", web, warnings)
    assert blended["status"] == "success"
    assert blended["provider"] == "mock"
    assert warnings

