"""Loads Scout's prompts from the scout/prompts folder.

The prompts live in plain text files so you can read and edit them
without touching any code (and so an agent can tune them in Chapter 14).
"""
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
