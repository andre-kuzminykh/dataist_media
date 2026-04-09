"""Configuration loader for the arXiv editorial pipeline.

Loads prompt profiles, style profiles, and HTML templates from JSON/HTML
files stored under service/config/. Separates configuration (prompts,
styles, templates) from business logic so that editorial content can be
iterated on independently of code changes.

Traceability
------------
- F003  – Configurable prompt & style profiles
- SC009 – Prompt profile schema (prompts/*.json)
- SC010 – Style profile schema  (styles/*.json)
- FR-11 – Prompts, styles, and templates stored separately from logic
- FR-12 – Profiles are versioned JSON; loader resolves by profile id
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_ROOT = Path(__file__).resolve().parent


class ConfigLoader:
    """Loads and caches pipeline configuration assets.

    All ``load_*`` helpers resolve files relative to the ``service/config/``
    directory.  Loaded JSON is cached in-memory so repeated calls within the
    same process are essentially free.

    Parameters
    ----------
    config_root : Path | str | None
        Override the default config root (``service/config/``).  Useful for
        tests that provide fixture directories.
    """

    def __init__(self, config_root: Path | str | None = None) -> None:
        self._root = Path(config_root) if config_root else _CONFIG_ROOT
        self._cache: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_prompt_profile(self, profile_id: str) -> dict:
        """Load a prompt profile by its identifier.

        Parameters
        ----------
        profile_id : str
            Filename stem inside ``config/prompts/``, e.g.
            ``"default_ai_editorial_v1"``.

        Returns
        -------
        dict
            The full parsed JSON of the prompt profile.

        Raises
        ------
        FileNotFoundError
            If the profile JSON does not exist (logged at ERROR level).
        """
        return self._load_json("prompts", profile_id)

    def load_style_profile(self, profile_id: str) -> dict:
        """Load a style / visual-identity profile by its identifier.

        Parameters
        ----------
        profile_id : str
            Filename stem inside ``config/styles/``, e.g.
            ``"cinematic_orange_violet_v1"``.

        Returns
        -------
        dict
            The full parsed JSON of the style profile.

        Raises
        ------
        FileNotFoundError
            If the profile JSON does not exist (logged at ERROR level).
        """
        return self._load_json("styles", profile_id)

    def load_html_template(self, template_id: str) -> str:
        """Load an HTML template by its identifier.

        Parameters
        ----------
        template_id : str
            Filename stem inside ``config/templates/``, e.g.
            ``"article_page_v1"``.

        Returns
        -------
        str
            The raw HTML content of the template.

        Raises
        ------
        FileNotFoundError
            If the template file does not exist (logged at ERROR level).
        """
        cache_key = f"templates/{template_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self._root / "templates" / f"{template_id}.html"
        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error("HTML template not found: %s", path)
            raise

        self._cache[cache_key] = content
        return content

    def get_prompt(self, profile_id: str, prompt_name: str, **kwargs: Any) -> str:
        """Return a ready-to-use prompt string with placeholders filled in.

        Loads the prompt profile, looks up *prompt_name* inside its
        ``prompts`` mapping, and calls :py:meth:`str.format_map` with the
        supplied *kwargs*.

        Parameters
        ----------
        profile_id : str
            Prompt profile identifier (see :meth:`load_prompt_profile`).
        prompt_name : str
            Key inside the profile's ``"prompts"`` dict (e.g. ``"editorial"``,
            ``"title"``, ``"cover"``).
        **kwargs
            Values for the ``{placeholder}`` variables in the prompt template.

        Returns
        -------
        str
            The formatted prompt text.

        Raises
        ------
        FileNotFoundError
            If the prompt profile does not exist.
        KeyError
            If *prompt_name* is not present in the profile.
        """
        profile = self.load_prompt_profile(profile_id)
        prompts = profile.get("prompts", {})

        if prompt_name not in prompts:
            raise KeyError(
                f"Prompt '{prompt_name}' not found in profile '{profile_id}'. "
                f"Available prompts: {list(prompts.keys())}"
            )

        template = prompts[prompt_name]
        return template.format_map(kwargs)

    def get_glossary(self, profile_id: str) -> dict:
        """Return the glossary dictionary from a prompt profile.

        Parameters
        ----------
        profile_id : str
            Prompt profile identifier.

        Returns
        -------
        dict
            Term -> translation mapping.  Returns an empty dict if the
            profile has no ``"glossary"`` key.

        Raises
        ------
        FileNotFoundError
            If the prompt profile does not exist.
        """
        profile = self.load_prompt_profile(profile_id)
        return profile.get("glossary", {})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_json(self, subdirectory: str, file_id: str) -> dict:
        """Load and cache a JSON file from *subdirectory/file_id.json*."""
        cache_key = f"{subdirectory}/{file_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self._root / subdirectory / f"{file_id}.json"
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error("Config file not found: %s", path)
            raise

        data = json.loads(raw)
        self._cache[cache_key] = data
        return data
