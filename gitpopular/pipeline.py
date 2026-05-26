from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from .ai import Analyzer, OpenAIAnalyzer, looks_ai_related
from .archive import GHArchiveClient
from .github import GitHubClient
from .models import DailyReport, RankedRepo
from .renderer import write_outputs


@dataclass(frozen=True)
class PipelineConfig:
    report_date: date
    timezone: str = "Asia/Shanghai"
    limit: int = 10
    candidate_pool: int = 100
    min_ai_confidence: float = 0.55
    require_exact_limit: bool = True
    output_root: Path = Path(".")


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
