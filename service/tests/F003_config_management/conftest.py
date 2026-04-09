"""
Feature-specific fixtures for F003 — Configurable Prompt & Style Profiles.

Creates temporary config directories with sample JSON files for testing
ConfigLoader without touching real config files.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def sample_prompt_profile() -> dict:
    """A minimal prompt profile dict for testing."""
    return {
        "id": "test_prompt_v1",
        "version": 1,
        "prompts": {
            "editorial": (
                "Write an article about: {abstract}\n"
                "Using text: {article_text}\n"
                "Figures: {figures_info}\n"
                "Glossary: {glossary}"
            ),
            "title": "Generate a title for: {short_intro}",
            "subtitle": "Generate subtitle for {title}: {short_intro}",
            "cover": (
                "Create an image for: {article_summary}\n"
                "Palette: {palette}\nMood: {mood}"
            ),
            "teaser": "Write a teaser for {title} in {language}: {short_intro}",
            "link_extraction": "Extract links from: {article_text}",
            "translation": "Translate to English: {article_body}",
        },
        "glossary": {
            "Transformer": "Трансформер",
            "Attention": "Внимание",
            "Fine-tuning": "Дообучение",
        },
    }


@pytest.fixture()
def sample_style_profile() -> dict:
    """A minimal style profile dict for testing."""
    return {
        "id": "test_style_v1",
        "version": 1,
        "palette_names": ["deep orange", "electric violet", "midnight blue"],
        "mood": "cinematic and futuristic",
        "background": "dark gradient",
        "typography": "modern sans-serif",
    }


@pytest.fixture()
def config_dir(tmp_path, sample_prompt_profile, sample_style_profile):
    """Create a temporary config directory with prompts/ and styles/ sub-dirs.

    Returns the path to the config root directory (equivalent to
    service/config/).
    """
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    styles_dir = tmp_path / "styles"
    styles_dir.mkdir()

    # Write sample prompt profile
    prompt_file = prompts_dir / "test_prompt_v1.json"
    prompt_file.write_text(json.dumps(sample_prompt_profile), encoding="utf-8")

    # Write sample style profile
    style_file = styles_dir / "test_style_v1.json"
    style_file.write_text(json.dumps(sample_style_profile), encoding="utf-8")

    return tmp_path
