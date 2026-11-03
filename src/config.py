from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

def get_setting(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is not None and not value.strip():
        return default
    return value

DATABASE_URL = get_setting("DATABASE_URL")
OPENAI_API_KEY = get_setting("OPENAI_API_KEY")
OPENAI_MODEL = get_setting("OPENAI_MODEL", "gpt-4.1-mini")
STALE_DAYS = int(get_setting("STALE_DAYS", "14") or "14")
MAX_TOOL_ROUNDS = int(get_setting("MAX_TOOL_ROUNDS", "4") or "4")
