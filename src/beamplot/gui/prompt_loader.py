"""Load prompt templates from V1/src/assets/prompt/ directory."""
from __future__ import annotations

from pathlib import Path

_PROMPT_DIR = Path(__file__).parents[2] / "assets" / "prompt"

_cache: dict[str, str] = {}


def load_prompt(category: str, lang: str = "zh") -> str:
    """Load a prompt template by category and language.

    Args:
        category: One of 'citation', 'median', 'publication', 'region',
                  'system', 'system_general'.
        lang: 'zh' or 'en'.

    Returns:
        The raw template string with {placeholders} for .format().
    """
    key = f"{category}:{lang}"
    if key in _cache:
        return _cache[key]

    if category == "system_general":
        path = _PROMPT_DIR / "system" / f"{lang}_general.txt"
    else:
        path = _PROMPT_DIR / category / f"{lang}.txt"

    if not path.exists():
        return ""

    text = path.read_text(encoding="utf-8").strip()
    _cache[key] = text
    return text
