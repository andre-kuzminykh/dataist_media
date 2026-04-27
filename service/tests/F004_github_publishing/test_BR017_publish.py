"""
Test BR017 — GitHub publish to date folder.

## Traceability
Feature: F004 — GitHub Publishing
Scenario: SC015 — Articles auto-published to GitHub
Business rule: BR017 — Date-based folder publishing

## BDD
Given: GitHubPublisherService configured with token + repo
When:  publish() is called
Then:  Returns html_url and cover_url with GitHub Pages domain
"""

from unittest.mock import AsyncMock, patch

import pytest

from service.core.config import config
from service.service.pipeline.github_publisher_service import GitHubPublisherService


class TestPublishWithToken:
    """BR017_1: With valid token, publish returns proper URLs."""

    @pytest.mark.asyncio
    async def test_publish_returns_urls(self):
        """
        Given: Token set, folder_name provided
        When:  publish() called
        Then:  Returns dict with html_url + cover_url
        """
        original_token = config.GITHUB_TOKEN
        original_repo = config.GITHUB_REPO
        original_pages = config.GITHUB_PAGES_URL

        config.GITHUB_TOKEN = "test_token"
        config.GITHUB_REPO = "owner/repo"
        config.GITHUB_PAGES_URL = "https://test.example.com"

        try:
            svc = GitHubPublisherService()
            with patch.object(svc, "_put_file", new=AsyncMock(return_value=None)):
                result = await svc.publish(
                    html_content="<html></html>",
                    cover_image=b"fake-png",
                    folder_name="2026-04-27",
                )

            assert result["folder"] == "2026-04-27"
            assert result["html_url"] == "https://test.example.com/2026-04-27/"
            assert result["cover_url"] == "https://test.example.com/2026-04-27/cover.png"
        finally:
            config.GITHUB_TOKEN = original_token
            config.GITHUB_REPO = original_repo
            config.GITHUB_PAGES_URL = original_pages


class TestPublishWithoutToken:
    """BR017_2: Without token, publish returns empty without errors."""

    @pytest.mark.asyncio
    async def test_publish_skipped_when_no_token(self):
        """
        Given: Token empty
        When:  publish() called
        Then:  Returns empty html_url, no HTTP requests
        """
        original_token = config.GITHUB_TOKEN
        config.GITHUB_TOKEN = ""

        try:
            svc = GitHubPublisherService()
            with patch.object(
                svc, "_put_file",
                new=AsyncMock(side_effect=AssertionError("should not be called")),
            ):
                result = await svc.publish(
                    html_content="<html></html>",
                    cover_image=b"fake",
                    folder_name="2026-04-27",
                )

            assert result["html_url"] == ""
            assert result["cover_url"] == ""
        finally:
            config.GITHUB_TOKEN = original_token


class TestFindAvailableFolder:
    """BR018: Folder suffix _1, _2, ... when name taken."""

    @pytest.mark.asyncio
    async def test_returns_base_when_free(self):
        """
        Given: Base folder doesn't exist
        When:  _find_available_folder(base) called
        Then:  Returns base unchanged
        """
        original_token = config.GITHUB_TOKEN
        config.GITHUB_TOKEN = "test"
        try:
            svc = GitHubPublisherService()
            with patch.object(svc, "_folder_exists", new=AsyncMock(return_value=False)):
                result = await svc._find_available_folder("2026-04-27")
            assert result == "2026-04-27"
        finally:
            config.GITHUB_TOKEN = original_token

    @pytest.mark.asyncio
    async def test_returns_suffix_when_taken(self):
        """
        Given: 2026-04-27 and 2026-04-27_1 exist, _2 free
        When:  _find_available_folder called
        Then:  Returns "2026-04-27_2"
        """
        original_token = config.GITHUB_TOKEN
        config.GITHUB_TOKEN = "test"
        try:
            svc = GitHubPublisherService()
            existing = {"2026-04-27", "2026-04-27_1"}

            async def fake_exists(folder: str) -> bool:
                return folder in existing

            with patch.object(svc, "_folder_exists", new=fake_exists):
                result = await svc._find_available_folder("2026-04-27")
            assert result == "2026-04-27_2"
        finally:
            config.GITHUB_TOKEN = original_token

    @pytest.mark.asyncio
    async def test_returns_higher_suffix(self):
        """
        Given: Base + _1.._5 exist
        When:  _find_available_folder called
        Then:  Returns "_6"
        """
        original_token = config.GITHUB_TOKEN
        config.GITHUB_TOKEN = "test"
        try:
            svc = GitHubPublisherService()
            existing = {"2026-04-27"} | {f"2026-04-27_{i}" for i in range(1, 6)}

            async def fake_exists(folder: str) -> bool:
                return folder in existing

            with patch.object(svc, "_folder_exists", new=fake_exists):
                result = await svc._find_available_folder("2026-04-27")
            assert result == "2026-04-27_6"
        finally:
            config.GITHUB_TOKEN = original_token
