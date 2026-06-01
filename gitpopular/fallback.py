from __future__ import annotations

import re

from .ai import TEXT_PATTERNS, TOPIC_KEYWORDS
from .models import AnalysisResult, RawRepo


CAPABILITY_RULES = [
    (r"\b(llm|large language model|gpt|claude|gemini|llama|ollama|mistral)\b", "大语言模型"),
    (r"\b(agent|agents|agentic|workflow|automation|mcp)\b", "智能体与自动化工作流"),
    (r"\b(rag|retrieval|embedding|vector database|knowledge graph|memory)\b", "知识检索与上下文增强"),
    (r"\b(code|coding|developer|repository|codebase|programming)\b", "AI 编程与代码理解"),
    (r"\b(image|video|audio|speech|tts|multimodal|diffusion|stable diffusion)\b", "多媒体生成与理解"),
    (r"\b(machine learning|deep learning|training|fine[- ]?tuning|inference|model)\b", "模型训练与推理"),
    (r"\b(computer vision|ocr|detection|segmentation)\b", "计算机视觉"),
    (r"\b(nlp|language|translation|chatbot)\b", "自然语言处理"),
    (r"\b(sdk|api|framework|library|toolkit)\b", "开发框架与 SDK"),
    (r"\b(design|prototype|figma|ui|ux)\b", "AI 设计与原型生成"),
    (r"\b(course|tutorial|learning|education|from scratch)\b", "AI 学习与教程"),
]

SCENARIO_RULES = [
    (
        r"\b(code|coding|developer|repository|codebase|programming)\b",
        "接入团队研发流程，辅助代码库理解、重构评估、文档生成或 AI 编程助手的上下文构建。",
    ),
    (
        r"\b(agent|agents|agentic|workflow|automation|mcp)\b",
        "作为智能体工作流的基础组件，连接工具、数据源和业务系统，完成半自动化任务编排。",
    ),
    (
        r"\b(rag|retrieval|embedding|vector database|knowledge graph|memory)\b",
        "用于企业知识库、客服问答或研发资料检索，提升大模型回答的准确性和可追溯性。",
    ),
    (
        r"\b(image|video|audio|speech|tts|multimodal|diffusion|stable diffusion)\b",
        "搭建内容生产流水线，批量生成或处理营销素材、短视频、语音内容和多模态资产。",
    ),
    (
        r"\b(machine learning|deep learning|training|fine[- ]?tuning|inference|model)\b",
        "用于模型实验、推理服务验证或内部 AI 平台选型，降低从研究到原型的落地成本。",
    ),
    (
        r"\b(design|prototype|figma|ui|ux)\b",
        "辅助产品和设计团队快速生成界面原型、设计系统草案或多版本视觉方案。",
    ),
    (
        r"\b(course|tutorial|learning|education|from scratch)\b",
        "作为学习材料或内部培训项目，帮助团队系统掌握相关 AI 工程方法。",
    ),
]

GENERIC_SCENARIOS = [
    "作为同类开源方案的调研对象，评估其 README、示例和社区活跃度后决定是否引入。",
    "基于项目提供的示例搭建内部原型，验证它与现有数据、工具链或业务流程的集成成本。",
    "跟踪其快速增长背后的功能方向，为产品路线、技术选型或竞品分析提供参考。",
]


def build_fallback_analysis(item: RawRepo) -> AnalysisResult:
    text = _combined_text(item)
    capabilities = _matched_labels(text)
    if not capabilities:
        capabilities = ["AI 相关能力"]

    description = _compact(item.description) or _readme_title(item.readme_text) or item.repo
    project_name = item.repo.split("/")[-1]
    capability_text = "、".join(capabilities[:4])
    language = item.language or "未知语言"

    purpose = (
        f"{project_name} 主要围绕「{description}」展开，结合 README、topics 和仓库描述来看，"
        f"可用于{capability_text}相关的开源实践、集成或学习。"
    )
    summary = (
        f"该项目以 {language} 为主要语言，近期新增 stars 较快。"
        f"本地兜底解析识别到的核心信号包括{capability_text}；"
        "建议进一步阅读原始 README 来确认安装方式、依赖条件和生产可用性。"
    )

    return AnalysisResult(
        ai_related=True,
        ai_confidence=_fallback_confidence(item, text),
        summary_zh=summary,
        purpose_zh=purpose,
        application_scenarios_zh=_scenarios(text),
    )


def _combined_text(item: RawRepo) -> str:
    return "\n".join([item.repo, item.description, " ".join(item.topics), item.readme_text[:12_000]]).lower()


def _matched_labels(text: str) -> list[str]:
    labels: list[str] = []
    for pattern, label in CAPABILITY_RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            labels.append(label)
    return _dedupe(labels)


def _fallback_confidence(item: RawRepo, text: str) -> float:
    topics = {topic.lower() for topic in item.topics}
    topic_hits = len(topics & TOPIC_KEYWORDS)
    text_hits = sum(1 for pattern in TEXT_PATTERNS if re.search(pattern, text, flags=re.IGNORECASE))
    score = 0.58 + min(topic_hits * 0.06 + text_hits * 0.015, 0.37)
    return round(min(score, 0.95), 2)


def _scenarios(text: str) -> list[str]:
    matched = [scenario for pattern, scenario in SCENARIO_RULES if re.search(pattern, text, flags=re.IGNORECASE)]
    return _dedupe(matched + GENERIC_SCENARIOS)[:3]


def _readme_title(readme_text: str) -> str:
    for line in readme_text.splitlines():
        cleaned = line.strip().lstrip("#").strip()
        if cleaned:
            return _compact(cleaned)
    return ""


def _compact(value: str, limit: int = 180) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
