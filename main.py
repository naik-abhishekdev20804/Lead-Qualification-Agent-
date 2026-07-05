"""CLI entry point — run a single prompt through the agent.

Usage:
    uv run python main.py "Tell me about lead L-001"
    uv run python main.py            (uses a default demo prompt)

For interactive chat with a web UI, use:  uv run adk web
"""

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

from app.agent import root_agent  # noqa: E402
from config import settings  # noqa: E402

DEFAULT_PROMPT = "List all leads in the CRM and tell me which one looks most promising."


async def run(prompt: str) -> None:
    session_service = InMemorySessionService()
    await session_service.create_session(app_name="app", user_id="cli_user", session_id="cli")
    runner = Runner(agent=root_agent, app_name="app", session_service=session_service)

    print(f"\n>>> {prompt}\n")
    async for event in runner.run_async(
        user_id="cli_user",
        session_id="cli",
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            print(event.content.parts[0].text)


if __name__ == "__main__":
    if not settings.google_api_key or settings.google_api_key.startswith("your-"):
        print("ERROR: GOOGLE_API_KEY is not set.")
        print("Copy .env.example to .env and add your Gemini API key")
        print("(free at https://aistudio.google.com/apikey), then rerun.")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:]) or DEFAULT_PROMPT
    asyncio.run(run(prompt))
