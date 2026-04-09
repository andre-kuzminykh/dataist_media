"""
Test SC009 — Prompt profile loading.

Feature: F003 — Configurable Prompt & Style Profiles
Scenario: SC009 — Loading and using prompt profiles

Verifies that ConfigLoader.load_prompt_profile loads valid JSON,
get_prompt formats templates correctly, get_glossary returns the
glossary dict, and FileNotFoundError is raised for missing profiles.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from service.config.config_loader import ConfigLoader


# ---------------------------------------------------------------------------
# load_prompt_profile
# ---------------------------------------------------------------------------

class TestLoadPromptProfile:
    """Tests for loading prompt profiles from disk."""

    def test_loads_valid_json(self, config_dir: Path) -> None:
        """
        Given a valid prompt profile JSON file in the config directory
        When load_prompt_profile is called with its ID
        Then it returns a dict with prompts and glossary keys.
        """
        loader = ConfigLoader(config_root=config_dir)
        profile = loader.load_prompt_profile("test_prompt_v1")

        assert isinstance(profile, dict)
        assert "prompts" in profile
        assert "glossary" in profile

    def test_profile_contains_expected_prompts(self, config_dir: Path) -> None:
        """
        Given a prompt profile with editorial, title, cover prompts
        When load_prompt_profile is called
        Then all prompt keys are present.
        """
        loader = ConfigLoader(config_root=config_dir)
        profile = loader.load_prompt_profile("test_prompt_v1")
        prompts = profile["prompts"]

        assert "editorial" in prompts
        assert "title" in prompts
        assert "cover" in prompts
        assert "teaser" in prompts

    def test_raises_file_not_found_for_missing_profile(self, config_dir: Path) -> None:
        """
        Given a profile ID that does not exist
        When load_prompt_profile is called
        Then FileNotFoundError is raised.
        """
        loader = ConfigLoader(config_root=config_dir)

        with pytest.raises(FileNotFoundError):
            loader.load_prompt_profile("nonexistent_profile")

    def test_profile_id_and_version_present(
        self, config_dir: Path, sample_prompt_profile: dict,
    ) -> None:
        """
        Given a prompt profile with id and version fields
        When load_prompt_profile is called
        Then those fields are accessible.
        """
        loader = ConfigLoader(config_root=config_dir)
        profile = loader.load_prompt_profile("test_prompt_v1")

        assert profile["id"] == sample_prompt_profile["id"]
        assert profile["version"] == sample_prompt_profile["version"]


# ---------------------------------------------------------------------------
# get_prompt
# ---------------------------------------------------------------------------

class TestGetPrompt:
    """Tests for get_prompt template formatting."""

    def test_formats_template_correctly(self, config_dir: Path) -> None:
        """
        Given a prompt template with {short_intro} placeholder
        When get_prompt is called with short_intro='test summary'
        Then the placeholder is replaced in the returned string.
        """
        loader = ConfigLoader(config_root=config_dir)
        result = loader.get_prompt(
            "test_prompt_v1",
            "title",
            short_intro="Neural networks improve accuracy",
        )

        assert "Neural networks improve accuracy" in result
        assert "{short_intro}" not in result

    def test_formats_editorial_template(self, config_dir: Path) -> None:
        """
        Given the editorial prompt template with multiple placeholders
        When get_prompt is called with all required kwargs
        Then all placeholders are filled.
        """
        loader = ConfigLoader(config_root=config_dir)
        result = loader.get_prompt(
            "test_prompt_v1",
            "editorial",
            abstract="We study transformers.",
            article_text="Full article text here.",
            figures_info="Figure 1: Architecture",
            glossary="Transformer: model type",
        )

        assert "We study transformers." in result
        assert "Full article text here." in result
        assert "{abstract}" not in result

    def test_raises_key_error_for_unknown_prompt_name(self, config_dir: Path) -> None:
        """
        Given a valid profile
        When get_prompt is called with a prompt_name that does not exist
        Then KeyError is raised.
        """
        loader = ConfigLoader(config_root=config_dir)

        with pytest.raises(KeyError, match="not_a_real_prompt"):
            loader.get_prompt(
                "test_prompt_v1",
                "not_a_real_prompt",
            )

    def test_raises_file_not_found_for_missing_profile(self, config_dir: Path) -> None:
        """
        Given a profile ID that does not exist
        When get_prompt is called
        Then FileNotFoundError is raised.
        """
        loader = ConfigLoader(config_root=config_dir)

        with pytest.raises(FileNotFoundError):
            loader.get_prompt("missing_profile", "title", short_intro="x")

    def test_cover_prompt_with_all_vars(self, config_dir: Path) -> None:
        """
        Given the cover prompt template
        When get_prompt is called with article_summary, palette, mood
        Then all variables are substituted.
        """
        loader = ConfigLoader(config_root=config_dir)
        result = loader.get_prompt(
            "test_prompt_v1",
            "cover",
            article_summary="A study on attention mechanisms",
            palette="orange, violet",
            mood="dramatic",
        )

        assert "A study on attention mechanisms" in result
        assert "orange, violet" in result
        assert "dramatic" in result


# ---------------------------------------------------------------------------
# get_glossary
# ---------------------------------------------------------------------------

class TestGetGlossary:
    """Tests for glossary retrieval."""

    def test_returns_glossary_dict(self, config_dir: Path) -> None:
        """
        Given a prompt profile with a glossary section
        When get_glossary is called
        Then it returns a dict with term->translation mappings.
        """
        loader = ConfigLoader(config_root=config_dir)
        glossary = loader.get_glossary("test_prompt_v1")

        assert isinstance(glossary, dict)
        assert len(glossary) > 0

    def test_glossary_contains_expected_terms(self, config_dir: Path) -> None:
        """
        Given a glossary with Transformer, Attention, Fine-tuning
        When get_glossary is called
        Then those terms are present as keys.
        """
        loader = ConfigLoader(config_root=config_dir)
        glossary = loader.get_glossary("test_prompt_v1")

        assert "Transformer" in glossary
        assert "Attention" in glossary
        assert "Fine-tuning" in glossary

    def test_glossary_values_are_translations(
        self, config_dir: Path, sample_prompt_profile: dict,
    ) -> None:
        """
        Given a glossary with known translations
        When get_glossary is called
        Then values match the expected translations.
        """
        loader = ConfigLoader(config_root=config_dir)
        glossary = loader.get_glossary("test_prompt_v1")

        expected = sample_prompt_profile["glossary"]
        for term, translation in expected.items():
            assert glossary[term] == translation

    def test_raises_file_not_found_for_missing_profile(self, config_dir: Path) -> None:
        """
        Given a missing profile ID
        When get_glossary is called
        Then FileNotFoundError is raised.
        """
        loader = ConfigLoader(config_root=config_dir)

        with pytest.raises(FileNotFoundError):
            loader.get_glossary("nonexistent_profile")

    def test_empty_glossary_returns_empty_dict(self, tmp_path: Path) -> None:
        """
        Given a prompt profile with no glossary key
        When get_glossary is called
        Then it returns an empty dict.
        """
        import json

        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "no_glossary.json").write_text(
            json.dumps({"prompts": {"title": "test"}}),
            encoding="utf-8",
        )

        loader = ConfigLoader(config_root=tmp_path)
        glossary = loader.get_glossary("no_glossary")

        assert glossary == {}
