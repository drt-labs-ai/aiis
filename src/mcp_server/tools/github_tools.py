"""GitHub MCP tools."""
from __future__ import annotations
import logging
import os
from typing import Any
import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _token() -> str:
    return os.getenv("GITHUB_TOKEN", "")


def _repo() -> str:
    return os.getenv("GITHUB_REPO", "")


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    tok = _token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


async def assign_issue(issue_number: int, assignees: list[str]) -> dict[str, Any]:
    """Assign GitHub issue to team members."""
    if not _token() or not _repo():
        return {"mock": True, "issue_number": issue_number, "assignees": assignees, "message": "GitHub not configured; mock response"}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{_repo()}/issues/{issue_number}/assignees",
            headers=_headers(),
            json={"assignees": assignees},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


async def add_labels(issue_number: int, labels: list[str]) -> dict[str, Any]:
    """Add labels to a GitHub issue."""
    if not _token() or not _repo():
        return {"mock": True, "issue_number": issue_number, "labels": labels}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{_repo()}/issues/{issue_number}/labels",
            headers=_headers(),
            json={"labels": labels},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


async def add_comment(issue_number: int, body: str) -> dict[str, Any]:
    """Add a comment to a GitHub issue."""
    if not _token() or not _repo():
        logger.info(f"Mock GitHub comment on issue #{issue_number}:\n{body[:200]}...")
        return {"mock": True, "issue_number": issue_number, "body_preview": body[:100]}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{_repo()}/issues/{issue_number}/comments",
            headers=_headers(),
            json={"body": body},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


async def search_issues(query: str, repo: str | None = None) -> list[dict[str, Any]]:
    """Search GitHub issues for similar problems."""
    target_repo = repo or _repo()
    if not _token() or not target_repo:
        return [
            {"mock": True, "number": 42, "title": f"Similar issue: {query[:50]}", "state": "closed", "body": "This was resolved by clearing the cache."},
            {"mock": True, "number": 38, "title": "Previous related incident", "state": "closed", "body": "Root cause was a misconfigured feature flag."},
        ]

    search_query = f"{query} repo:{target_repo} is:issue"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/search/issues",
            headers=_headers(),
            params={"q": search_query, "per_page": 5},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("items", [])
