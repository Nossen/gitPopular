from __future__ import annotations

import pytest

from gitpopular.ai import OpenAIAnalyzer, looks_ai_related, parse_analysis_payload
from gitpopular.models import RepoMetadata


def make_repo(**overrides: object) -> RepoMetadata:
    data = {
        "repo": "owner/repo",
        "repo_id": 1,
        "url": "https://github.com/owner/repo",
        "description": "A regular project",
        "language": "Python",
        "topics": [],
        "total_stars": 100,
        "readme_url": "https://github.com/owner/repo/blob/main/README.md",
        "readme_text": "Hello world",
    }
    data.update(overrides)
    return RepoMetadata(**data)


def test_looks_ai_related_matches_topics_description_and_readme() -> None:
    assert looks_ai_related(make_repo(topics=["llm"]))
    assert looks_ai_related(make_repo(description="A toolkit for generative AI workflows"))
    assert looks_ai_related(make_repo(readme_text="This project runs local large language models."))
    assert not looks_ai_related(make_repo(description="A CSS reset", readme_text="Tiny frontend helper."))


def test_parse_analysis_payload_requires_three_scenarios_and_confidence_range() -> None:
    result = parse_analysis_payload(
        {
            "ai_related": True,
            "ai_confidence": 0.91,
            "summary_zh": "摘要",
            "purpose_zh": "作用",
            "application_scenarios_zh": ["场景一", "场景二", "场景三"],
        }
    )

    assert result.ai_related is True
    assert result.ai_confidence == 0.91
    assert result.application_scenarios_zh == ["场景一", "场景二", "场景三"]


def test_parse_analysis_payload_rejects_invalid_scenarios() -> None:
    with pytest.raises(ValueError):
        parse_analysis_payload(
            {
                "ai_related": True,
                "ai_confidence": 0.91,
                "summary_zh": "摘要",
                "purpose_zh": "作用",
                "application_scenarios_zh": ["场景一"],
            }
        )


def test_openai_analyzer_parses_output_text_json() -> None:
    class Responses:
        def create(self, **kwargs: object) -> object:
            assert kwargs["model"] == "test-model"
            assert kwargs["text"]["format"]["type"] == "json_schema"
            return type(
                "Response",
                (),
                {
                    "output_text": (
                        '{"ai_related": true, "ai_confidence": 0.8, "summary_zh": "摘要", '
                        '"purpose_zh": "作用", "application_scenarios_zh": ["一", "二", "三"]}'
                    )
                },
            )()

    class Client:
        responses = Responses()

    analyzer = OpenAIAnalyzer(model="test-model", client=Client())

    result = analyzer.analyze(make_repo(topics=["llm"]))

    assert result.ai_related
    assert result.summary_zh == "摘要"
