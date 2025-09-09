from pathlib import Path

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.txt").read_text()
