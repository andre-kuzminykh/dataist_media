"""
Test SC010 — Style profile loading.

Feature: F003 — Configurable Prompt & Style Profiles
Scenario: SC010 — Loading and caching style profiles

Verifies that ConfigLoader.load_style_profile loads valid JSON,
that repeated loads return the same cached object, and that
FileNotFoundError is raised for missing style profiles.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from service.config.config_loader import ConfigLoader


# ---------------------------------------------------------------------------
# load_style_profile — happy path
# ---------------------------------------------------------------------------

class TestLoadStyleProfile:
    """Tests for loading style profiles from disk."""

    def test_loads_valid_json(self, config_dir: Path) -> None:
        """
        Given a valid style profile JSON file
        When load_style_profile is called
        Then it returns a dict with palette and mood keys.
        """
        loader = ConfigLoader(config_root=config_dir)
        profile = loader.load_style_profile("test_style_v1")

        assert isinstance(profile, dict)
        assert "palette_names" in profile
        assert "mood" in profile

    def test_palette_names_is_list(self, config_dir: Path) -> None:
        """
        Given a style profile with palette_names array
        When load_style_profile is called
        Then palette_names is a list of strings.
        """
        loader = ConfigLoader(config_root=config_dir)
        profile = loader.load_style_profile("test_style_v1")

        assert isinstance(profile["palette_names"], list)
        assert all(isinstance(c, str) for c in profile["palette_names"])

    def test_mood_is_string(self, config_dir: Path) -> None:
        """
        Given a style profile with mood field
        When load_style_profile is called
        Then mood is a non-empty string.
        """
        loader = ConfigLoader(config_root=config_dir)
        profile = loader.load_style_profile("test_style_v1")

        assert isinstance(profile["mood"], str)
        assert len(profile["mood"]) > 0

    def test_all_expected_fields_present(
        self, config_dir: Path, sample_style_profile: dict,
    ) -> None:
        """
        Given a style profile with known fields
        When load_style_profile is called
        Then all expected fields are present with correct values.
        """
        loader = ConfigLoader(config_root=config_dir)
        profile = loader.load_style_profile("test_style_v1")

        for key in sample_style_profile:
            assert key in profile, f"Missing key: {key}"
            assert profile[key] == sample_style_profile[key]


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

class TestStyleProfileCaching:
    """Tests that repeated loads return the cached object."""

    def test_second_load_returns_same_object(self, config_dir: Path) -> None:
        """
        Given a style profile that has been loaded once
        When load_style_profile is called again with the same ID
        Then it returns the exact same dict object (cached).
        """
        loader = ConfigLoader(config_root=config_dir)

        first = loader.load_style_profile("test_style_v1")
        second = loader.load_style_profile("test_style_v1")

        assert first is second  # Same object reference — cached

    def test_different_ids_are_not_cached_together(self, tmp_path: Path) -> None:
        """
        Given two different style profiles
        When each is loaded
        Then they are different objects.
        """
        import json

        styles_dir = tmp_path / "styles"
        styles_dir.mkdir()

        profile_a = {"id": "a", "palette_names": ["red"], "mood": "bold"}
        profile_b = {"id": "b", "palette_names": ["blue"], "mood": "calm"}

        (styles_dir / "style_a.json").write_text(
            json.dumps(profile_a), encoding="utf-8",
        )
        (styles_dir / "style_b.json").write_text(
            json.dumps(profile_b), encoding="utf-8",
        )

        loader = ConfigLoader(config_root=tmp_path)

        a = loader.load_style_profile("style_a")
        b = loader.load_style_profile("style_b")

        assert a is not b
        assert a["id"] == "a"
        assert b["id"] == "b"

    def test_cache_survives_multiple_calls(self, config_dir: Path) -> None:
        """
        Given a loader with cached data
        When the profile is loaded three times
        Then all three references point to the same object.
        """
        loader = ConfigLoader(config_root=config_dir)

        ref1 = loader.load_style_profile("test_style_v1")
        ref2 = loader.load_style_profile("test_style_v1")
        ref3 = loader.load_style_profile("test_style_v1")

        assert ref1 is ref2 is ref3


# ---------------------------------------------------------------------------
# Missing profile
# ---------------------------------------------------------------------------

class TestStyleProfileMissing:
    """Tests for missing style profile error handling."""

    def test_raises_file_not_found_for_missing_style(self, config_dir: Path) -> None:
        """
        Given a style profile ID that does not exist on disk
        When load_style_profile is called
        Then FileNotFoundError is raised.
        """
        loader = ConfigLoader(config_root=config_dir)

        with pytest.raises(FileNotFoundError):
            loader.load_style_profile("nonexistent_style")

    def test_error_does_not_corrupt_cache(self, config_dir: Path) -> None:
        """
        Given a failed load for a missing profile
        When load_style_profile is called for a valid profile afterwards
        Then the valid profile loads correctly.
        """
        loader = ConfigLoader(config_root=config_dir)

        with pytest.raises(FileNotFoundError):
            loader.load_style_profile("missing_one")

        # Valid profile should still load fine
        profile = loader.load_style_profile("test_style_v1")
        assert profile["id"] == "test_style_v1"
