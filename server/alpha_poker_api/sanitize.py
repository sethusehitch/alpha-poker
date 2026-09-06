from __future__ import annotations

import re

# Mirrors app/components/Leaderboard.tsx's CONTROL_CHARACTERS and the stripping
# rules in COMMUNITY_DESIGN_SPEC.md section 7.1: reject C0/C1 controls outright,
# strip bidi overrides/isolates (direction-spoofing) and zero-width characters.
CONTROL_CHARACTERS = re.compile(r"[\u0000-\u001f\u007f-\u009f]")
BIDI_FORMATTING = re.compile(r"[\u202a-\u202e\u2066-\u2069]")
ZERO_WIDTH = re.compile(r"[\u200b-\u200d\u2060\ufeff]")


def has_control_characters(value: str) -> bool:
    return bool(CONTROL_CHARACTERS.search(value))


def strip_invisible_formatting(value: str) -> str:
    return ZERO_WIDTH.sub("", BIDI_FORMATTING.sub("", value))


def clean_text(value: str) -> str:
    """Trim, reject C0/C1 controls, and strip bidi/zero-width formatting.

    Python strings are already sequences of Unicode code points, so plain
    ``len()``/slicing here is code-point-safe without needing an
    ``Array.from``-style helper the way the TypeScript side does.
    """
    trimmed = value.strip()
    if has_control_characters(trimmed):
        raise ValueError("Text contains control characters")
    return strip_invisible_formatting(trimmed)
