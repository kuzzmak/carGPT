import os
from pathlib import Path

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.txt").read_text()

CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o")
