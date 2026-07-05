"""Research summary formatting/limit tests."""

from app.services.research_service import _limit_research_summary
from config import settings


def test_limit_research_summary_respects_config_caps() -> None:
    summary = {
        "company_overview": "A" * 5000,
        "recent_news": "B" * 5000,
        "detailed_summary": "C" * 5000,
        "growth_signals": [f"g{i}" for i in range(20)],
        "tech_stack": [f"t{i}" for i in range(20)],
        "sources": [f"https://example.com/{i}" for i in range(20)],
        "official_website": "https://example.com",
    }
    limited = _limit_research_summary(summary)

    assert len(limited["company_overview"]) <= settings.research_overview_max_chars
    assert len(limited["recent_news"]) <= settings.research_news_max_chars
    assert len(limited["detailed_summary"]) <= settings.research_detailed_summary_max_chars
    assert len(limited["growth_signals"]) <= settings.research_max_growth_signals
    assert len(limited["tech_stack"]) <= settings.research_max_tech_stack
    assert len(limited["sources"]) <= settings.research_max_sources

