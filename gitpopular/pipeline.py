from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from .ai import Analyzer, OpenAIAnalyzer, looks_ai_related
from .archive import GHArchiveClient
from .github import GitHubClient
import json
from typing import Any

from .models import AnalysisResult, DailyReport, RankedRepo, RawReport, RawRepo
from .renderer import write_outputs, write_raw_outputs


@dataclass(frozen=True)
class PipelineConfig:
    report_date: date
    timezone: str = "Asia/Shanghai"
    limit: int = 10
    candidate_pool: int = 100
    min_ai_confidence: float = 0.55
    require_exact_limit: bool = True
    output_root: Path = Path(".")
    readme_char_limit: int = 80_000


def run_pipeline(
    config: PipelineConfig,
    archive_client: GHArchiveClient | None = None,
    github_client: GitHubClient | None = None,
    analyzer: Analyzer | None = None,
    now: datetime | None = None,
) -> DailyReport:
    archive_client = archive_client or GHArchiveClient()
    github_client = github_client or GitHubClient()
    analyzer = analyzer or OpenAIAnalyzer()

    growths = archive_client.fetch_daily_growth(config.report_date, config.timezone)
    items: list[RankedRepo] = []

    for growth in growths[: config.candidate_pool]:
        metadata = github_client.fetch_metadata(growth.repo_name, expected_repo_id=growth.repo_id)
        if metadata is None:
            continue
        if not looks_ai_related(metadata):
            continue

        analysis = analyzer.analyze(metadata)
        if not analysis.ai_related or analysis.ai_confidence < config.min_ai_confidence:
            continue

        items.append(
            RankedRepo(
                rank=len(items) + 1,
                repo=metadata.repo,
                repo_id=metadata.repo_id,
                url=metadata.url,
                description=metadata.description,
                language=metadata.language,
                topics=metadata.topics,
                yesterday_new_stars=growth.yesterday_new_stars,
                total_stars=metadata.total_stars,
                readme_url=metadata.readme_url,
                ai_confidence=analysis.ai_confidence,
                summary_zh=analysis.summary_zh,
                purpose_zh=analysis.purpose_zh,
                application_scenarios_zh=analysis.application_scenarios_zh,
            )
        )
        if len(items) >= config.limit:
            break

    if config.require_exact_limit and len(items) < config.limit:
        raise RuntimeError(
            f"Only found {len(items)} AI repositories from {config.candidate_pool} candidates; "
            f"expected {config.limit}. Increase --candidate-pool or inspect filters."
        )

    generated_at = (now or datetime.now(UTC)).astimezone(UTC).isoformat().replace("+00:00", "Z")
    report = DailyReport(
        date=config.report_date.isoformat(),
        timezone=config.timezone,
        generated_at=generated_at,
        source={
            "stars": "GH Archive WatchEvent",
            "metadata": "GitHub REST API",
            "analysis": "OpenAI Responses API",
        },
        items=items,
    )
    write_outputs(report, config.output_root)
    return report


def collect_raw_report(
    config: PipelineConfig,
    archive_client: GHArchiveClient | None = None,
    github_client: GitHubClient | None = None,
    now: datetime | None = None,
) -> RawReport:
    archive_client = archive_client or GHArchiveClient()
    github_client = github_client or GitHubClient()

    growths = archive_client.fetch_daily_growth(config.report_date, config.timezone)
    items: list[RawRepo] = []

    for growth in growths[: config.candidate_pool]:
        metadata = github_client.fetch_metadata(growth.repo_name, expected_repo_id=growth.repo_id)
        if metadata is None:
            continue
        if not looks_ai_related(metadata):
            continue

        items.append(
            RawRepo(
                rank=len(items) + 1,
                repo=metadata.repo,
                repo_id=metadata.repo_id,
                url=metadata.url,
                description=metadata.description,
                language=metadata.language,
                topics=metadata.topics,
                yesterday_new_stars=growth.yesterday_new_stars,
                total_stars=metadata.total_stars,
                readme_url=metadata.readme_url,
                readme_text=metadata.readme_text[: config.readme_char_limit],
            )
        )
        if len(items) >= config.limit:
            break

    if config.require_exact_limit and len(items) < config.limit:
        raise RuntimeError(
            f"Only collected {len(items)} AI repositories from {config.candidate_pool} candidates; "
            f"expected {config.limit}. Increase --candidate-pool or inspect filters."
        )

    report = RawReport(
        date=config.report_date.isoformat(),
        timezone=config.timezone,
        generated_at=_generated_at(now),
        source={
            "stars": "GH Archive WatchEvent",
            "metadata": "GitHub REST API",
            "ai_prefilter": "Local keyword/topic filter",
        },
        items=items,
    )
    write_raw_outputs(report, config.output_root)
    return report


def finalize_report_from_analysis(
    report_date: date,
    output_root: Path,
    analysis_path: Path | None = None,
    now: datetime | None = None,
) -> DailyReport:
    raw_path = output_root / "data" / "raw" / f"{report_date.isoformat()}.json"
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw report not found: {raw_path}")

    analysis_path = analysis_path or output_root / "data" / "analysis" / f"{report_date.isoformat()}.json"
    if not analysis_path.exists():
        raise FileNotFoundError(f"Analysis file not found: {analysis_path}")

    raw_report = RawReport.from_dict(json.loads(raw_path.read_text(encoding="utf-8")))
    analysis_by_repo = _load_analysis_by_repo(analysis_path)
    items: list[RankedRepo] = []

    for raw_item in raw_report.items:
        analysis = analysis_by_repo.get(raw_item.repo)
        if analysis is None:
            raise ValueError(f"Missing analysis for {raw_item.repo}")
        items.append(
            RankedRepo(
                rank=raw_item.rank,
                repo=raw_item.repo,
                repo_id=raw_item.repo_id,
                url=raw_item.url,
                description=raw_item.description,
                language=raw_item.language,
                topics=raw_item.topics,
                yesterday_new_stars=raw_item.yesterday_new_stars,
                total_stars=raw_item.total_stars,
                readme_url=raw_item.readme_url,
                ai_confidence=analysis.ai_confidence,
                summary_zh=analysis.summary_zh,
                purpose_zh=analysis.purpose_zh,
                application_scenarios_zh=analysis.application_scenarios_zh,
            )
        )

    report = DailyReport(
        date=raw_report.date,
        timezone=raw_report.timezone,
        generated_at=_generated_at(now),
        source={
            "stars": "GH Archive WatchEvent",
            "metadata": "GitHub REST API",
            "analysis": "Codex scheduled automation",
        },
        items=items,
    )
    write_outputs(report, output_root)
    return report


def _load_analysis_by_repo(path: Path) -> dict[str, AnalysisResult]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_items: list[dict[str, Any]]
    if isinstance(payload, dict):
        raw_items = payload.get("items") or []
    elif isinstance(payload, list):
        raw_items = payload
    else:
        raise ValueError("Analysis file must be a JSON object with items or a JSON list")

    analysis_by_repo: dict[str, AnalysisResult] = {}
    for item in raw_items:
        repo = str(item["repo"])
        scenarios = item.get("application_scenarios_zh")
        if not isinstance(scenarios, list) or len(scenarios) != 3:
            raise ValueError(f"Analysis for {repo} must include exactly three application scenarios")
        analysis_by_repo[repo] = AnalysisResult(
            ai_related=bool(item.get("ai_related", True)),
            ai_confidence=float(item.get("ai_confidence", 0.9)),
            summary_zh=str(item["summary_zh"]).strip(),
            purpose_zh=str(item["purpose_zh"]).strip(),
            application_scenarios_zh=[str(scenario).strip() for scenario in scenarios],
        )
    return analysis_by_repo


def _generated_at(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(UTC).isoformat().replace("+00:00", "Z")
