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

CAPABILITY_TAGS = {
    "大语言模型": "大模型",
    "智能体与自动化工作流": "智能体",
    "知识检索与上下文增强": "RAG",
    "AI 编程与代码理解": "AI 编程",
    "多媒体生成与理解": "多模态",
    "模型训练与推理": "模型推理",
    "计算机视觉": "视觉 AI",
    "自然语言处理": "NLP",
    "开发框架与 SDK": "开发工具",
    "AI 设计与原型生成": "AI 设计",
    "AI 学习与教程": "AI 教程",
    "AI 相关能力": "AI 工具",
}


def build_fallback_analysis(item: RawRepo) -> AnalysisResult:
    text = _combined_text(item)
    capabilities = _matched_labels(text)
    if not capabilities:
        capabilities = ["AI 相关能力"]
    capabilities = _prioritize_capabilities(item, text, capabilities)

    description = _compact(item.description) or _readme_title(item.readme_text) or item.repo
    project_name = item.repo.split("/")[-1]
    capability_text = "、".join(capabilities[:4])
    language = item.language or "未知语言"
    tags = _project_tags(item, capabilities)
    maturity_score = _maturity_score(item)
    recommendation_score = _recommendation_score(item, maturity_score)
    adoption_difficulty = _adoption_difficulty(item, text)
    positioning = _positioning(project_name, description, capabilities)

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
        positioning_zh=positioning,
        product_view_zh=_product_view(project_name, description, capabilities),
        technical_view_zh=_technical_view(item, text, language, capabilities, adoption_difficulty),
        trend_view_zh=_trend_view(item, capabilities),
        project_tags_zh=tags,
        maturity_score=maturity_score,
        adoption_difficulty=adoption_difficulty,
        recommendation_score=recommendation_score,
        adoption_notes_zh=_adoption_notes(adoption_difficulty),
    )


def _combined_text(item: RawRepo) -> str:
    return "\n".join([item.repo, item.description, " ".join(item.topics), item.readme_text[:12_000]]).lower()


def _matched_labels(text: str) -> list[str]:
    labels: list[str] = []
    for pattern, label in CAPABILITY_RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            labels.append(label)
    return _dedupe(labels)


def _prioritize_capabilities(item: RawRepo, text: str, capabilities: list[str]) -> list[str]:
    topic_text = " ".join(topic.lower() for topic in item.topics)
    repo_text = f"{item.repo} {item.description}".lower()
    priority_checks = [
        ("知识检索与上下文增强", r"\b(rag|retrieval|embedding|embeddings|vector|vector-search|ann|faiss)\b"),
        ("AI 编程与代码理解", r"\b(code-review|codex|claude-code|programming|codebase|repository)\b"),
        ("智能体与自动化工作流", r"\b(agent|agents|ai-skill|automation|workflow|mcp|skill)\b"),
        ("多媒体生成与理解", r"\b(image|video|audio|speech|tts|multimodal|diffusion)\b"),
        ("计算机视觉", r"\b(computer-vision|ocr|detection|segmentation)\b"),
        ("AI 设计与原型生成", r"\b(design|prototype|figma|ui|ux)\b"),
        ("模型训练与推理", r"\b(training|fine-tuning|inference|quantization|model)\b"),
        ("开发框架与 SDK", r"\b(sdk|api|framework|library|toolkit)\b"),
        ("AI 学习与教程", r"\b(course|tutorial|learning|education|from-scratch)\b"),
    ]
    search_text = f"{topic_text} {repo_text} {text[:4000]}"
    for label, pattern in priority_checks:
        if label in capabilities and re.search(pattern, search_text, flags=re.IGNORECASE):
            return [label] + [capability for capability in capabilities if capability != label]
    return capabilities


def _fallback_confidence(item: RawRepo, text: str) -> float:
    topics = {topic.lower() for topic in item.topics}
    topic_hits = len(topics & TOPIC_KEYWORDS)
    text_hits = sum(1 for pattern in TEXT_PATTERNS if re.search(pattern, text, flags=re.IGNORECASE))
    score = 0.58 + min(topic_hits * 0.06 + text_hits * 0.015, 0.37)
    return round(min(score, 0.95), 2)


def _scenarios(text: str) -> list[str]:
    matched = [scenario for pattern, scenario in SCENARIO_RULES if re.search(pattern, text, flags=re.IGNORECASE)]
    return _dedupe(matched + GENERIC_SCENARIOS)[:3]


def _project_tags(item: RawRepo, capabilities: list[str]) -> list[str]:
    topic_tags = [_topic_to_tag(topic) for topic in item.topics]
    tags = [tag for tag in topic_tags if tag]
    tags.extend(CAPABILITY_TAGS.get(capability, capability) for capability in capabilities)
    if item.language:
        tags.append(item.language)
    tags.append("高增长")
    return _dedupe(tags)[:5] or ["AI 工具", "开源项目", "高增长"]


def _topic_to_tag(topic: str) -> str:
    mapping = {
        "agent": "智能体",
        "agents": "智能体",
        "ai-agent": "智能体",
        "ai-agents": "智能体",
        "automation": "自动化",
        "claude-code": "AI 编程",
        "code-review": "代码审查",
        "codex": "AI 编程",
        "embedding": "向量检索",
        "embeddings": "向量检索",
        "llm": "大模型",
        "mcp": "MCP",
        "openai": "OpenAI",
        "rag": "RAG",
        "security": "安全",
    }
    return mapping.get(topic.lower(), "")


def _maturity_score(item: RawRepo) -> int:
    if item.total_stars >= 100_000:
        return 5
    if item.total_stars >= 20_000:
        return 4
    if item.total_stars >= 3_000:
        return 3
    return 2


def _recommendation_score(item: RawRepo, maturity_score: int) -> int:
    growth_score = 2 if item.yesterday_new_stars >= 100 else 1
    return max(1, min(5, maturity_score + growth_score - 1))


def _adoption_difficulty(item: RawRepo, text: str) -> str:
    if re.search(r"\b(self-hosted|deploy|docker|kubernetes|server|database)\b", text, flags=re.IGNORECASE):
        return "高"
    if item.language in {"Shell", None}:
        return "低"
    return "中"


def _positioning(project_name: str, description: str, capabilities: list[str]) -> str:
    primary = capabilities[0]
    if primary == "智能体与自动化工作流":
        return f"{project_name} 是一个智能体/自动化工作流项目，核心目标是「{description}」。"
    if primary == "知识检索与上下文增强":
        return f"{project_name} 聚焦检索增强与知识上下文构建，主要解决「{description}」。"
    if primary == "AI 编程与代码理解":
        return f"{project_name} 面向代码理解、审查或研发协作场景，主要能力是「{description}」。"
    if primary == "多媒体生成与理解":
        return f"{project_name} 面向图像、音频、视频等多模态内容处理，核心卖点是「{description}」。"
    if primary == "模型训练与推理":
        return f"{project_name} 偏模型实验、训练或推理工程，主要围绕「{description}」展开。"
    if primary == "开发框架与 SDK":
        return f"{project_name} 是面向开发者集成的框架/SDK 型项目，提供「{description}」。"
    return f"{project_name} 是一个大模型相关开源项目，核心目标是「{description}」。"


def _product_view(project_name: str, description: str, capabilities: list[str]) -> str:
    primary = capabilities[0]
    capability_text = "、".join(capabilities[:3])
    if primary == "智能体与自动化工作流":
        return (
            f"从产品/应用角度看，{project_name} 更像一个流程中枢：把工具调用、上下文和任务步骤组织起来。"
            f"如果团队正在把「{description}」落到真实工作流，它可以作为原型底座，用来验证自动化是否能减少人工切换。"
        )
    if primary == "知识检索与上下文增强":
        return (
            f"从产品/应用角度看，{project_name} 的价值在于提升知识查找和大模型回答的可用性。"
            f"它适合用于「{description}」这类需要向量检索、召回质量或上下文管理的场景。"
        )
    if primary == "AI 编程与代码理解":
        return (
            f"从产品/应用角度看，{project_name} 主要服务研发效率。"
            f"它把「{description}」包装成可试用的开源能力，适合评估代码审查、代码库理解或开发协作流程中的 AI 增益。"
        )
    return (
        f"从产品/应用角度看，{project_name} 的价值在于把「{description}」对应的问题转成可复用工具或参考实现。"
        f"它适合正在评估{capability_text}方案的个人开发者、产品团队或技术团队，用来快速验证场景是否成立。"
    )


def _technical_view(item: RawRepo, text: str, language: str, capabilities: list[str], difficulty: str) -> str:
    capability_text = "、".join(capabilities[:3])
    stack_signals = _stack_signals(item, text)
    return (
        f"技术选型上，它主要以 {language} 实现，{stack_signals}。"
        f"README 和 topics 暗示其核心能力集中在{capability_text}。"
        f"当前接入难度评估为「{difficulty}」，建议先检查安装方式、依赖服务、示例完整度和许可证。"
    )


def _trend_view(item: RawRepo, capabilities: list[str]) -> str:
    primary = capabilities[0]
    capability_text = "、".join(capabilities[:3])
    trend_hint = {
        "智能体与自动化工作流": "智能体正在从演示走向可执行工作流",
        "知识检索与上下文增强": "RAG 和向量检索仍是企业落地大模型的基础设施入口",
        "AI 编程与代码理解": "AI 编程工具正在从补全走向代码库级理解和审查",
        "多媒体生成与理解": "多模态能力正在进入内容生产和素材处理链路",
        "模型训练与推理": "模型推理、量化和训练工具仍在快速工程化",
    }.get(primary, f"社区正在关注{capability_text}方向")
    return (
        f"趋势上，该项目昨日新增 {item.yesterday_new_stars:,} stars，反映出：{trend_hint}。"
        "如果后续 issue、release 和文档继续活跃，它可能成为同类方案选型时值得跟踪的候选。"
    )


def _stack_signals(item: RawRepo, text: str) -> str:
    signals: list[str] = []
    for pattern, label in [
        (r"\brust\b", "Rust"),
        (r"\bpython bindings?\b", "Python bindings"),
        (r"\bdocker\b", "Docker"),
        (r"\bmcp\b", "MCP"),
        (r"\bcli\b", "CLI"),
        (r"\bapi\b", "API"),
        (r"\btypescript\b", "TypeScript"),
        (r"\bserver\b", "服务端组件"),
    ]:
        if re.search(pattern, text, flags=re.IGNORECASE):
            signals.append(label)
    signals = [signal for signal in signals if signal != item.language]
    if not signals:
        return "当前可见的工程信号主要来自 README、topics 和仓库语言"
    return "可见工程信号包括" + "、".join(_dedupe(signals)[:4])


def _adoption_notes(difficulty: str) -> list[str]:
    notes = [
        "先用 README 示例搭建最小原型，确认核心能力是否符合预期。",
        "检查许可证、release 节奏、issue 响应和关键依赖，避免只被短期热度影响。",
    ]
    if difficulty == "高":
        notes.append("涉及自托管或服务端部署时，优先评估数据安全、运维成本和可观测性。")
    elif difficulty == "低":
        notes.append("适合先作为个人或团队工作流插件试用，再决定是否沉淀为标准流程。")
    else:
        notes.append("接入业务前建议做一次小规模集成测试，验证配置、性能和边界条件。")
    return notes


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
