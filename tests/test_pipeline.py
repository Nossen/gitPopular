from __future__ import annotations

import json
from datetime import UTC, date, datetime

from gitpopular.models import AnalysisResult, RepoMetadata, StarGrowth
from gitpopular.pipeline import (
    PipelineConfig,
    collect_raw_report,
    finalize_report_from_analysis,
    finalize_report_with_fallback_analysis,
    run_pipeline,
)


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
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    daily = (tmp_path / "reports" / "2026-05-25.md").read_text(encoding="utf-8")
    assert "### 1." not in readme
    assert "一句话亮点" in readme
    assert "## 社媒速读版" in daily
    assert "👉01" in daily
    assert "<details open>" in daily


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
                        "positioning_zh": "owner/ai-one 的一句话定位",
                        "product_view_zh": "owner/ai-one 的产品价值",
                        "technical_view_zh": "owner/ai-one 的技术观察",
                        "trend_view_zh": "owner/ai-one 的趋势判断",
                        "category_zh": "AI 编程工作流",
                        "highlight_zh": "owner/ai-one 的一句话亮点",
                        "target_users_zh": ["研发团队", "AI 工具调研者"],
                        "best_use_case_zh": "owner/ai-one 的最佳场景",
                        "not_suitable_zh": "owner/ai-one 的不适合场景",
                        "project_tags_zh": ["AI 编程", "RAG", "开发工具"],
                        "maturity_score": 4,
                        "adoption_difficulty": "中",
                        "recommendation_score": 5,
                        "application_scenarios_zh": ["场景一", "场景二", "场景三"],
                        "adoption_notes_zh": ["建议一", "建议二", "建议三"],
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
    assert payload["items"][0]["positioning_zh"] == "owner/ai-one 的一句话定位"
    assert payload["items"][0]["category_zh"] == "AI 编程工作流"
    assert payload["items"][0]["highlight_zh"] == "owner/ai-one 的一句话亮点"
    assert payload["items"][0]["target_users_zh"] == ["研发团队", "AI 工具调研者"]
    assert payload["items"][0]["best_use_case_zh"] == "owner/ai-one 的最佳场景"
    assert payload["items"][0]["not_suitable_zh"] == "owner/ai-one 的不适合场景"
    assert payload["items"][0]["project_tags_zh"][:3] == ["AI 编程", "RAG", "开发工具"]
    assert 3 <= len(payload["items"][0]["project_tags_zh"]) <= 5
    assert payload["items"][0]["maturity_score"] == 4
    assert payload["items"][0]["adoption_difficulty"] == "中"
    assert payload["items"][0]["recommendation_score"] == 5
    assert payload["items"][0]["adoption_notes_zh"] == ["建议一", "建议二", "建议三"]
    assert payload["items"][1]["project_tags_zh"][:3] == ["AI 工具", "开源项目", "开发者工具"]
    assert payload["items"][1]["highlight_zh"]
    assert len(payload["items"][1]["target_users_zh"]) >= 2


def test_fallback_finalize_writes_final_outputs_without_analysis_json(tmp_path) -> None:
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

    report = finalize_report_with_fallback_analysis(
        report_date=date(2026, 5, 25),
        output_root=tmp_path,
        now=datetime(2026, 5, 26, 2, 30, tzinfo=UTC),
    )

    assert len(report.items) == 2
    assert (tmp_path / "README.md").exists()
    assert (tmp_path / "reports" / "2026-05-25.md").exists()
    payload = json.loads((tmp_path / "data" / "2026-05-25.json").read_text(encoding="utf-8"))
    assert payload["source"]["analysis"] == "Local heuristic fallback"
    assert payload["items"][0]["ai_confidence"] >= 0.55
    assert len(payload["items"][0]["project_tags_zh"]) >= 3
    assert payload["items"][0]["category_zh"]
    assert payload["items"][0]["highlight_zh"]
    assert len(payload["items"][0]["target_users_zh"]) >= 2
    assert payload["items"][0]["best_use_case_zh"]
    assert payload["items"][0]["not_suitable_zh"]
    assert 1 <= payload["items"][0]["maturity_score"] <= 5
    assert payload["items"][0]["adoption_difficulty"] in {"低", "中", "高"}
    assert 1 <= payload["items"][0]["recommendation_score"] <= 5
    assert len(payload["items"][0]["application_scenarios_zh"]) == 3
    assert len(payload["items"][0]["adoption_notes_zh"]) == 3
    daily = (tmp_path / "reports" / "2026-05-25.md").read_text(encoding="utf-8")
    assert "## 社媒速读版" in daily
    assert "项目类别" in daily
    assert "适合人群" in daily
    assert "最佳使用场景" in daily
    assert "不适合场景" in daily
    assert "#### 产品/应用价值" in daily
    assert "#### 技术选型观察" in daily
    assert "#### 趋势判断" in daily
    assert "#### 采用建议" in daily
