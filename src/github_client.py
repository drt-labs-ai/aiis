"""GitHub client for issue operations."""
from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from typing import Any
import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")


@dataclass
class GitHubIssue:
    number: int
    title: str
    body: str
    labels: list[str]
    state: str
    author: str
    url: str


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


async def get_issue(issue_number: int) -> GitHubIssue | None:
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return GitHubIssue(
            number=issue_number,
            title=f"Mock Issue #{issue_number}",
            body="This is a mock issue body for testing.",
            labels=["bug"],
            state="open",
            author="test-user",
            url=f"https://github.com/mock/repo/issues/{issue_number}",
        )
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{GITHUB_REPO}/issues/{issue_number}",
            headers=_headers(),
            timeout=10,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return GitHubIssue(
            number=data["number"],
            title=data["title"],
            body=data.get("body") or "",
            labels=[l["name"] for l in data.get("labels", [])],
            state=data["state"],
            author=data["user"]["login"],
            url=data["html_url"],
        )
