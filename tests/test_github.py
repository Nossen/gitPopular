from __future__ import annotations

import base64
import json

import httpx

from gitpopular.github import GitHubClient


def test_fetch_metadata_decodes_readme_and_skips_repository_flags() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/owner/repo":
            return httpx.Response(
                200,
                json={
                    "id": 123,
                    "full_name": "owner/repo",
                    "html_url": "https://github.com/owner/repo",
                    "description": "AI toolkit",
                    "language": "Python",
                    "topics": ["llm"],
                    "stargazers_count": 42,
                    "archived": False,
                    "disabled": False,
                    "fork": False,
                },
            )
        if request.url.path == "/repos/owner/repo/readme":
            encoded = base64.b64encode(b"# Repo\nAI README").decode()
            return httpx.Response(
                200,
                json={
                    "encoding": "base64",
                    "content": encoded,
                    "html_url": "https://github.com/owner/repo/blob/main/README.md",
                },
            )
        return httpx.Response(404, json={"message": "not found"})

    client = GitHubClient(client=httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler)))

    metadata = client.fetch_metadata("owner/repo", expected_repo_id=123)

    assert metadata is not None
    assert metadata.repo == "owner/repo"
    assert metadata.readme_text == "# Repo\nAI README"
    assert metadata.topics == ["llm"]


def test_fetch_metadata_returns_none_when_readme_is_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/owner/repo":
            return httpx.Response(
                200,
                json={
                    "id": 123,
                    "full_name": "owner/repo",
                    "html_url": "https://github.com/owner/repo",
                    "description": "",
                    "language": None,
                    "topics": [],
                    "stargazers_count": 0,
                    "archived": False,
                    "disabled": False,
                    "fork": False,
                },
            )
        return httpx.Response(404, content=json.dumps({"message": "not found"}))

    client = GitHubClient(client=httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler)))

    assert client.fetch_metadata("owner/repo", expected_repo_id=123) is None


def test_fetch_metadata_skips_archived_disabled_or_forked_repositories() -> None:
    for flag in ("archived", "disabled", "fork"):
        def handler(request: httpx.Request, flag: str = flag) -> httpx.Response:
            payload = {
                "id": 123,
                "full_name": "owner/repo",
                "html_url": "https://github.com/owner/repo",
                "description": "",
                "language": None,
                "topics": [],
                "stargazers_count": 0,
                "archived": False,
                "disabled": False,
                "fork": False,
            }
            payload[flag] = True
            return httpx.Response(200, json=payload)

        client = GitHubClient(
            client=httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
        )
        assert client.fetch_metadata("owner/repo", expected_repo_id=123) is None
