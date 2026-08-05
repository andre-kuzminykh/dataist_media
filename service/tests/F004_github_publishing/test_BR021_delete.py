"""
Test BR021 — Delete published article folder from GitHub.

## Traceability
Feature: F004 — GitHub Publishing
Scenario: SC018 — Delete published article via bot
Business rule: BR021 — User can delete a published article from the repo

## BDD
Given: Folder YYYY-MM-DD contains cover.png and index.html
When:  delete_folder(folder) is called
Then:  DELETE requests are issued for every file and True is returned
"""

from __future__ import annotations

import httpx
import pytest
import respx

from service.core.config import config
from service.service.pipeline.github_publisher_service import (
    GitHubPublisherService,
)

_API = "https://api.github.com"


@pytest.fixture()
def gh_config():
    """Temporarily configure a token and repo, restoring originals after."""
    original_token = config.GITHUB_TOKEN
    original_repo = config.GITHUB_REPO
    config.GITHUB_TOKEN = "test_token"
    config.GITHUB_REPO = "owner/repo"
    yield
    config.GITHUB_TOKEN = original_token
    config.GITHUB_REPO = original_repo


class TestDeleteFolder:
    """BR021: delete_folder removes every file of a published article."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_deletes_all_files_and_returns_true(self, gh_config):
        """
        Given: Folder 2026-04-27 contains cover.png and index.html
        When:  delete_folder("2026-04-27") is called
        Then:  A DELETE request is sent for each file and True is returned
        """
        folder = "2026-04-27"
        listing = [
            {"path": f"{folder}/cover.png", "sha": "sha-cover"},
            {"path": f"{folder}/index.html", "sha": "sha-index"},
        ]
        respx.get(f"{_API}/repos/owner/repo/contents/{folder}").mock(
            return_value=httpx.Response(200, json=listing)
        )
        delete_cover = respx.request(
            "DELETE", f"{_API}/repos/owner/repo/contents/{folder}/cover.png"
        ).mock(return_value=httpx.Response(200, json={"commit": {}}))
        delete_index = respx.request(
            "DELETE", f"{_API}/repos/owner/repo/contents/{folder}/index.html"
        ).mock(return_value=httpx.Response(200, json={"commit": {}}))

        svc = GitHubPublisherService()
        result = await svc.delete_folder(folder)

        assert result is True
        assert delete_cover.called
        assert delete_index.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_requests_carry_sha_and_branch(self, gh_config):
        """
        Given: A folder with one file
        When:  delete_folder is called
        Then:  The DELETE payload contains the file sha and branch main
        """
        folder = "2026-04-27"
        respx.get(f"{_API}/repos/owner/repo/contents/{folder}").mock(
            return_value=httpx.Response(
                200, json=[{"path": f"{folder}/index.html", "sha": "abc123"}]
            )
        )
        delete_route = respx.request(
            "DELETE", f"{_API}/repos/owner/repo/contents/{folder}/index.html"
        ).mock(return_value=httpx.Response(200, json={"commit": {}}))

        svc = GitHubPublisherService()
        await svc.delete_folder(folder)

        import json

        request = delete_route.calls[0].request
        payload = json.loads(request.content)
        assert payload["sha"] == "abc123"
        assert payload["branch"] == "main"

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_false_when_folder_missing(self, gh_config):
        """
        Given: The folder does not exist in the repo (404)
        When:  delete_folder is called
        Then:  False is returned and no DELETE requests are sent
        """
        respx.get(f"{_API}/repos/owner/repo/contents/2026-01-01").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )

        svc = GitHubPublisherService()
        result = await svc.delete_folder("2026-01-01")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_without_token(self):
        """
        Given: GITHUB_TOKEN is not configured
        When:  delete_folder is called
        Then:  False is returned without any HTTP requests
        """
        original_token = config.GITHUB_TOKEN
        config.GITHUB_TOKEN = ""
        try:
            svc = GitHubPublisherService()
            result = await svc.delete_folder("2026-04-27")
            assert result is False
        finally:
            config.GITHUB_TOKEN = original_token

    @pytest.mark.asyncio
    @respx.mock
    async def test_files_without_sha_are_skipped(self, gh_config):
        """
        Given: The listing contains an entry without sha
        When:  delete_folder is called
        Then:  That entry is skipped and no DELETE is attempted for it
        """
        folder = "2026-04-27"
        respx.get(f"{_API}/repos/owner/repo/contents/{folder}").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"path": f"{folder}/broken.png", "sha": ""},
                    {"path": f"{folder}/index.html", "sha": "ok-sha"},
                ],
            )
        )
        delete_ok = respx.request(
            "DELETE", f"{_API}/repos/owner/repo/contents/{folder}/index.html"
        ).mock(return_value=httpx.Response(200, json={"commit": {}}))

        svc = GitHubPublisherService()
        result = await svc.delete_folder(folder)

        assert result is True
        assert delete_ok.called
