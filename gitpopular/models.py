from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StarGrowth:
    repo_id: int
    repo_name: str
    yesterday_new_stars: int
    actor_ids: frozenset[int] = field(default_factory=frozenset, repr=False, compare=False)


@dataclass(frozen=True)
class RepoMetadata:
    repo: str
    repo_id: int
    url: str
    description: str
    language: str | None
    topics: list[str]
    total_stars: int
    readme_url: str
    readme_text: str


@dataclass(frozen=True)
class AnalysisResult:
    ai_related: bool
    ai_confidence: float
    summary_zh: str
    purpose_zh: str
    application_scenarios_zh: list[str]


@dataclass(frozen=True)
class RankedRepo:
    rank: int
    repo: str
    repo_id: int
    url: str
    description: str
    language: str | None
    topics: list[str]
    yesterday_new_stars: int
    total_stars: int
    readme_url: str
    ai_confidence: float
    summary_zh: str
    purpose_zh: str
    application_scenarios_zh: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "repo": self.repo,
            "repo_id": self.repo_id,
            "url": self.url,
            "description": self.description,
            "language": self.language,
            "topics": self.topics,
            "yesterday_new_stars": self.yesterday_new_stars,
            "total_stars": self.total_stars,
            "readme_url": self.readme_url,
            "ai_confidence": self.ai_confidence,
            "summary_zh": self.summary_zh,
            "purpose_zh": self.purpose_zh,
            "application_scenarios_zh": self.application_scenarios_zh,
        }


@dataclass(frozen=True)
class RawRepo:
    rank: int
    repo: str
    repo_id: int
    url: str
    description: str
    language: str | None
    topics: list[str]
    yesterday_new_stars: int
    total_stars: int
    readme_url: str
    readme_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "repo": self.repo,
            "repo_id": self.repo_id,
            "url": self.url,
            "description": self.description,
            "language": self.language,
            "topics": self.topics,
            "yesterday_new_stars": self.yesterday_new_stars,
            "total_stars": self.total_stars,
            "readme_url": self.readme_url,
            "readme_text": self.readme_text,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RawRepo":
        return cls(
            rank=int(payload["rank"]),
            repo=str(payload["repo"]),
            repo_id=int(payload["repo_id"]),
            url=str(payload["url"]),
            description=str(payload.get("description") or ""),
            language=payload.get("language"),
            topics=[str(topic) for topic in payload.get("topics") or []],
            yesterday_new_stars=int(payload["yesterday_new_stars"]),
            total_stars=int(payload["total_stars"]),
            readme_url=str(payload["readme_url"]),
            readme_text=str(payload.get("readme_text") or ""),
        )


@dataclass(frozen=True)
class RawReport:
    date: str
    timezone: str
    generated_at: str
    source: dict[str, str]
    items: list[RawRepo]

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "timezone": self.timezone,
            "generated_at": self.generated_at,
            "source": self.source,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RawReport":
        return cls(
            date=str(payload["date"]),
            timezone=str(payload["timezone"]),
            generated_at=str(payload["generated_at"]),
            source={str(key): str(value) for key, value in (payload.get("source") or {}).items()},
            items=[RawRepo.from_dict(item) for item in payload.get("items") or []],
        )


@dataclass(frozen=True)
class DailyReport:
    date: str
    timezone: str
    generated_at: str
    source: dict[str, str]
    items: list[RankedRepo]

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "timezone": self.timezone,
            "generated_at": self.generated_at,
            "source": self.source,
            "items": [item.to_dict() for item in self.items],
        }
