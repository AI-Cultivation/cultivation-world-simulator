"""Localized writing-style prompts used by generated story events."""

from __future__ import annotations

import random

from src.i18n import t


STORY_STYLE_KEYS: tuple[str, ...] = (
    "story_style.plain_narration",
    "story_style.emotion_in_scenery",
    "story_style.freehand_ancient",
    "story_style.marketplace_life",
    "story_style.poetic_lyricism",
    "story_style.philosophical_fable",
    "story_style.chronicle",
    "story_style.personified_scenery",
    "story_style.taoist_nature",
    "story_style.buddhist_emptiness",
    "story_style.folk_storytelling",
    "story_style.elegant_scholarly",
    "story_style.bold_and_open",
    "story_style.gorgeous_and_bizarre",
    "story_style.cold_and_concise",
    "story_style.fine_line_drawing",
)


def get_random_story_style() -> str:
    """Return one writing-style instruction in the active locale."""
    return t(random.choice(STORY_STYLE_KEYS))


__all__ = ["STORY_STYLE_KEYS", "get_random_story_style"]
