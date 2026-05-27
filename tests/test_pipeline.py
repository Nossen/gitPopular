from __future__ import annotations

import json
from datetime import UTC, date, datetime

from gitpopular.models import AnalysisResult, RepoMetadata, StarGrowth
from gitpopular.pipeline import PipelineConfig, collect_raw_report, finalize_report_from_analysis, run_pipeline


class FakeArchiveClient:
    def fetch_daily_growth(self, report_date: date, timezone_name: str) -> list[StarGrowth]:
        assert report_date == date(2026, 5, 25)
        assert timezone_name == "Asia/Shanghai"
        return [
            StarGrowth(1, "owner/ai-one", 30, frozenset({1, 2, 3})),
            StarGrowth(2, "owner/ai-two", 20, frozenset({4, 5})),
        ]


class FakeGitHubClient:
    def fetch_metadata(self, full_name: str, expected_repo_id: int | None = None) -> RepoMetadata | None:
        repo_id = expected_repo_id or 0
        return RepoMetadata(
            repo=full_name,
            repo_id=repo_id,
            url=f"https://github.com/{full_name}",
            description="LLM project",
            language="Python",
            topics=["llm"],
            total_stars=100 + repo_id,
            readme_url=f"https://github.com/{full_name}/blob/main/README.md",
            readme_text="# LLM project\nA useful AI repository.",
        )


class FakeAnalyzer:
    def analyze(self, repo: RepoMetadata) -> AnalysisResult:
        return AnalysisResult(
            ai_related=True,
            ai_confidence=0.9,
            summary_zh=f"{repo.repo} 的摘要",
            purpose_zh=f"{repo.repo} 的作用",
            application_scenarios_zh=["场景一", "场景二", "场景三"],
        )


def test_run_pipeline_writes_readme_daily_report_and_json(tmp_path) -> None:
    report = run_pipeline(
        PipelineConfig(
            report_date=date(2026, 5, 25),
            timezone="Asia/Shanghai",
            limit=2,
            candidate_pool=2,
            output_root=tmp_path,
        ),
        archive_client=FakeArchiveClient(),
        github_client=FakeGitHubClient(),
        analyzer=FakeAnalyzer(),
        now=datetime(2026, 5, 26, 1, 30, tzinfo=UTC),
    )

    assert len(report.items) == 2
    assert (tmp_path / "README.md").exists()
    assert (tmp_path / "reports" / "2026-05-25.md").exists()
    assert (tmp_path / "data" / "2026-05-25.json").exists()
    assert (tmp_path / "data" / "latest.json").exists()

    payload = json.loads((tmp_path / "data" / "latest.json").read_text(encoding="utf-8"))
    assert payload["date"] == "2026-05-25"
    assert payload["items"][0]["repo"] == "owner/ai-one"
    assert payload["items"][0]["yesterday_new_stars"] == 30


def test_collect_raw_report_writes_raw_json_and_markdown(tmp_path) -> None:
    report = collect_raw_report(
        PipelineConfig(
            report_date=date(2026, 5, 25),
            timezone="Asia/Shanghai",
            limit=2,
            candidate_pool=2,
            output_root=tmp_path,
            readme_char_limit=12,
        ),
        archive_client=FakeArchiveClient(),
        github_client=FakeGitHubClient(),
        now=datetime(2026, 5, 26, 1, 30, tzinfo=UTC),
    )

    assert len(report.items) == 2
    assert (tmp_path / "data" / "raw" / "2026-05-25.json").exists()
    assert (tmp_path / "data" / "raw" / "latest.json").exists()
    assert (tmp_path / "reports" / "raw" / "2026-05-25.md").exists()

    payload = json.loads((tmp_path / "data" / "raw" / "2026-05-25.json").read_text(encoding="utf-8"))
    assert payload["items"][0]["repo"] == "owner/ai-one"
    assert payload["items"][0]["readme_text"] == "# LLM projec"


def test_finalize_report_from_codex_analysis_writes_final_outputs(tmp_path) -> None:
    collect_raw_report(
        PipelineConfig(
            report_date=date(2026, 5, 25),
            timezone="Asia/Shanghai",
            limit=2,
            candidate_pool=2,
            output_root=tmp_path,
        ),
        archive_client=FakeArchiveClient(),
        github_client=FakeGitHubClient(),
        now=datetime(2026, 5, 26, 1, 30, tzinfo=UTC),
    )
    analysis_dir = tmp_path / "data" / "analysis"
    analysis_dir.mkdir(parents=True)
    analysis_path = analysis_dir / "2026-05-25.json"
    analysis_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "repo": "owner/ai-one",
                        "ai_confidence": 0.93,
                        "summary_zh": "owner/ai-one 的中文解析",
                        "purpose_zh": "owner/ai-one 的项目作用",
                        "application_scenarios_zh": ["场景一", "场景二", "场景三"],
                    },
                    {
                        "repo": "owner/ai-two",
                        "ai_confidence": 0.88,
                        "summary_zh": "owner/ai-two 的中文解析",
                        "purpose_zh": "owner/ai-two 的项目作用",
                        "application_scenarios_zh": ["场景一", "场景二", "场景三"],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = finalize_report_from_analysis(
        report_date=date(2026, 5, 25),
        output_root=tmp_path,
        analysis_path=analysis_path,
        now=datetime(2026, 5, 26, 2, 30, tzinfo=UTC),
    )

    assert len(report.items) == 2
    assert (tmp_path / "README.md").exists()
    assert (tmp_path / "reports" / "2026-05-25.md").exists()
    payload = json.loads((tmp_path / "data" / "2026-05-25.json").read_text(encoding="utf-8"))
    assert payload["source"]["analysis"] == "Codex scheduled automation"
    assert payload["items"][0]["purpose_zh"] == "owner/ai-one 的项目作用"
