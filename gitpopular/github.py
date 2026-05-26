from __future__ import annotations

import base64
import os
from typing import Any

import httpx

from .models import RepoMetadata


class GitHubClient:
    def __init__(self, token: str | None = None, client: httpx.Client | None = None) -> None:
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self.client = client or httpx.Client(
            base_url="https://api.github.com",
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers=self._headers(),
        )

    def fetch_metadata(self, full_name: str, expected_repo_id: int | None = None) -> RepoMetadata | None:
        repo = self._get_repo(full_name)
        if repo is None:
            return None
        if expected_repo_id is not None and repo.get("id") != expected_repo_id:
            return None
        if repo.get("archived") or repo.get("disabled") or repo.get("fork"):
            return None

        readme = self._get_readme(full_name)
        if readme is None:
            return None
        readme_text, readme_url = readme

        return RepoMetadata(
            repo=repo.get("full_name") or full_name,
            repo_id=int(repo["id"]),
            url=repo.get("html_url") or f"https://github.com/{full_name}",
            description=repo.get("description") or "",
            language=repo.get("language"),
            topics=list(repo.get("topics") or []),
            total_stars=int(repo.get("stargazers_count") or 0),
            readme_url=readme_url,
            readme_text=readme_text,
        )

    def _get_repo(self, full_name: str) -> dict[str, Any] | None:
        response = self.client.get(f"/repos/{full_name}", headers=self._headers())
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def _get_readme(self, full_name: str) -> tuple[str, str] | None:
        response = self.client.get(f"/repos/{full_name}/readme", headers=self._headers())
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        if payload.get("encoding") != "base64" or not payload.get("content"):
            return None
        text = base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
        url = payload.get("html_url") or payload.get("download_url") or f"https://github.com/{full_name}"
        return text, url

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "gitpopular-ai-rising-stars",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
