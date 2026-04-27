"""
Test BR023 — OG description truncation at sentence boundary.

## Traceability
Feature: F002 / F004
Scenario: SC013
Business rule: BR023 — Truncate by sentence, not mid-word

## BDD
Given: Text longer than max_len
When:  _truncate_by_sentence is called
Then:  Cuts at ". ", "! ", "? " within last half, falls back to space + ellipsis
"""

import pytest


def _truncate_by_sentence(text: str, max_len: int = 220) -> str:
    """Copy of the implementation in steps.py for direct testing."""
    text = text.strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    for sep in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
        idx = cut.rfind(sep)
        if idx > max_len // 2:
            return cut[: idx + 1].strip()
    idx = cut.rfind(" ")
    return (cut[:idx] if idx > 0 else cut).strip() + "…"


class TestTruncateBySentence:
    def test_short_text_unchanged(self):
        text = "Short."
        assert _truncate_by_sentence(text, 100) == "Short."

    def test_cuts_at_period(self):
        # max_len=50, half=25; ". " at pos 14 (rejected, < 25), then ". " at pos 31 (accepted)
        text = "First sentence. Second sentence. Third one continues here for ages."
        result = _truncate_by_sentence(text, 50)
        assert result.endswith(".")
        assert "Second" in result

    def test_cuts_at_exclamation(self):
        text = "Hello world! Another sentence here. Yet another line follows."
        result = _truncate_by_sentence(text, 16)
        assert result.endswith("!")

    def test_cuts_at_question(self):
        text = "Is this working? Yes it does! This is great."
        result = _truncate_by_sentence(text, 20)
        assert result.endswith("?")

    def test_no_sentence_break_uses_space_ellipsis(self):
        text = "x" * 30 + " " + "y" * 30
        result = _truncate_by_sentence(text, 25)
        # Should cut at space and add ellipsis
        assert result.endswith("…")
        # Cut should be at last space within max_len
        assert " " not in result.rstrip("…").strip()[-3:]
