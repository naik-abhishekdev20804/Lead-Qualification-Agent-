"""Generate OAuth token for Gmail send API."""

import sys
from pathlib import Path

# Allow running this file directly: `python scripts/setup_gmail_token.py`
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from config import PROJECT_ROOT, settings  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _resolve_project_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def main() -> int:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except Exception:
        print("google-auth-oauthlib is not installed. Run `python -m uv sync` first.")
        return 1

    creds_path = _resolve_project_path(settings.gmail_credentials_file)
    token_path = _resolve_project_path(settings.gmail_token_file)
    if not creds_path.exists():
        print(f"Gmail OAuth client file not found: {creds_path}")
        print("Download OAuth client JSON from Google Cloud Console and place it there.")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Gmail token saved to: {token_path}")
    print("Set GMAIL_SEND_ENABLED=TRUE and GMAIL_DEMO_TO_EMAIL in .env, then restart backend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

