"""Central configuration for Lead Qualification AI.

All settings load from `.env` (see `.env.example`). Import `settings`
from this module everywhere — never read `os.environ` directly in
agents, tools, or services (rule enforced by MASTER.md).
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent
CACHE_DIR = PROJECT_ROOT / ".cache"
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"


class Settings(BaseSettings):
    """Typed application settings, loaded once from `.env`."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gemini
    google_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"

    # External research providers
    tavily_api_key: str = ""
    serper_api_key: str = ""
    firecrawl_api_key: str = ""

    # API budget protection (see MASTER.md, section "API Budget Rules")
    mock_mode: bool = True
    cache_ttl_hours: int = 24
    daily_api_budget: int = 50

    # App
    log_level: str = "INFO"
    environment: str = "development"

    # Research output shaping (UI-friendly limits)
    research_overview_max_chars: int = 650
    research_news_max_chars: int = 700
    research_detailed_summary_max_chars: int = 2800
    research_max_growth_signals: int = 6
    research_max_tech_stack: int = 10
    research_max_sources: int = 10

    # Gmail delivery (real send on approve in live mode)
    gmail_send_enabled: bool = False
    gmail_demo_to_email: str = ""
    gmail_sender_email: str = ""
    gmail_subject_prefix: str = "[LeadPilot Demo]"
    gmail_credentials_file: str = "secrets/gmail_credentials.json"
    gmail_token_file: str = "secrets/gmail_token.json"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()

for _dir in (CACHE_DIR, LOG_DIR):
    _dir.mkdir(exist_ok=True)
