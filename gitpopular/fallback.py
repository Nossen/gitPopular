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
    category = _category(item, text, capabilities)
    tags = _project_tags(item, capabilities, category)
    maturity_score = _maturity_score(item)
    recommendation_score = _recommendation_score(item, maturity_score)
    adoption_difficulty = _adoption_difficulty(item, text)
    positioning = _positioning(project_name, description, capabilities, category)
    scenarios = _scenarios(text, category)

    purpose = (
        f"{project_name} 主要围绕「{description}」展开，结合 README、topics 和仓库描述来看，"
        f"可用于{capability_text}相关的开源实践、集成或学习。"
    )
    summary = (
        f"该项目以 {language} 为主要语言，近期新增 stars 较快。"
        f"综合 README、topics 和仓库描述可见的核心信号包括{capability_text}；"
        "建议结合原始 README、依赖条件、许可证和 issue 活跃度判断生产可用性。"
    )

    return AnalysisResult(
        ai_related=True,
        ai_confidence=_fallback_confidence(item, text),
        summary_zh=summary,
        purpose_zh=purpose,
        application_scenarios_zh=scenarios,
        positioning_zh=positioning,
        product_view_zh=_product_view(project_name, description, capabilities, category),
        technical_view_zh=_technical_view(item, text, language, capabilities, adoption_difficulty, category),
        trend_view_zh=_trend_view(item, capabilities, category),
        category_zh=category,
        highlight_zh=_highlight(project_name, description, category),
        target_users_zh=_target_users(category),
        best_use_case_zh=_best_use_case(project_name, category, scenarios),
        not_suitable_zh=_not_suitable(category, adoption_difficulty),
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


def _scenarios(text: str, category: str) -> list[str]:
    category_scenarios = {
        "文档转换": [
            "把 PDF、Office、网页或音视频转成 Markdown/文本，进入知识库、RAG 或 LLM 分析流程。",
            "为研究、投研、法务或运营资料建立统一的文本清洗入口。",
            "批量规范化历史资料，降低后续检索、摘要和问答系统的接入成本。",
        ],
        "AI 视频生产": [
            "搭建从选题、脚本、素材、字幕到配音的短视频自动化原型。",
            "批量生成营销素材、教程视频或产品演示草稿，再由人工做最终审核。",
            "把多模态生成能力嵌入内容工作流，验证低成本视频生产的可行性。",
        ],
        "联网 Agent": [
            "让研究型 Agent 自动读取公开网页、社媒和视频平台资料并生成报告。",
            "用于竞品监测、舆情观察、选题收集或公开信息尽调。",
            "把外部信息获取封装成可复用工具，接入内部 Agent 或自动化工作流。",
        ],
        "安全研究": [
            "在授权环境中组织逆向、安全测试、工具路由和知识库沉淀。",
            "把安全研究流程拆成可复用的 Agent 技能或命令链。",
            "为安全团队建立可审计的实验流程，降低重复配置工具链的成本。",
        ],
        "金融分析": [
            "自动汇总行情、公告、新闻和技术指标，形成可复核的投研看板。",
            "作为个人量化研究或团队晨报的原型工具。",
            "跟踪特定股票或行业主题，辅助发现需要人工进一步验证的信号。",
        ],
        "视觉/OCR": [
            "把图片、扫描件或复杂版面内容转成结构化文本，供检索和分析使用。",
            "为票据、合同、表格或多模态资料处理提供识别能力验证。",
            "作为文档自动化流水线的视觉入口，连接后续抽取、审核和归档。",
        ],
        "网站/前端生成": [
            "把自有或授权网站迁移到现代前端栈，并保留主要视觉和交互细节。",
            "用于前端学习、页面重构评估或设计还原原型验证。",
            "快速生成可修改的页面初稿，再由工程师补齐状态管理和业务逻辑。",
        ],
    }.get(category, [])
    matched = [scenario for pattern, scenario in SCENARIO_RULES if re.search(pattern, text, flags=re.IGNORECASE)]
    return _dedupe(category_scenarios + matched + GENERIC_SCENARIOS)[:3]


def _project_tags(item: RawRepo, capabilities: list[str], category: str) -> list[str]:
    category_tags = {
        "文档转换": ["文档转换", "RAG", "知识库"],
        "AI 视频生产": ["AI 视频", "内容生产", "多模态"],
        "上下文管理": ["上下文管理", "Agent", "Token 优化"],
        "联网 Agent": ["联网 Agent", "信息抓取", "自动化"],
        "视觉/OCR": ["OCR", "视觉 AI", "多模态"],
        "安全研究": ["安全研究", "工具链", "Agent"],
        "金融分析": ["金融分析", "投研", "自动化"],
        "网站/前端生成": ["前端生成", "网站复刻", "AI 编程"],
        "AI 编程工作流": ["AI 编程", "开发工具", "工作流"],
        "Agent 工具": ["智能体", "自动化", "工具调用"],
    }.get(category, [])
    topic_tags = [_topic_to_tag(topic) for topic in item.topics]
    tags = [*category_tags, *[tag for tag in topic_tags if tag]]
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


def _category(item: RawRepo, text: str, capabilities: list[str]) -> str:
    base = f"{item.repo} {item.description} {' '.join(item.topics)}".lower()
    readme = text[:5000]
    primary_checks = [
        ("AI 视频生产", r"\b(video-production|video generation|text-to-video|ffmpeg|remotion|subtitle)\b|短视频|视频生成|视频生产"),
        ("网站/前端生成", r"\b(website-clone|website cloner|clone.+website|shadcn-ui|nextjs|tailwindcss)\b|网站复刻|前端生成"),
        ("金融分析", r"\b(stock|finance|quant|trading|market)\b|股票|金融|量化"),
        ("视觉/OCR", r"\b(ocr|computer vision|image-generation|image generation|detection|segmentation)\b|视觉|图像|识别"),
        ("安全研究", r"\b(security|reverse|pentest|penetration|red team|malware)\b|安全|逆向|渗透"),
        ("联网 Agent", r"\b(web-scraper|twitter|reddit|youtube|bilibili|xiaohongshu|search|browser)\b|联网|社媒|搜索"),
        ("上下文管理", r"\b(context compression|context management|conversation memory|memory|token)\b|上下文|记忆|压缩"),
        ("AI 编程工作流", r"\b(claude-code|codex|cursor|code review|codebase|developer tools?|agent-skills|cursor-rules)\b|代码|编程"),
        ("RAG/知识库", r"\b(rag|retrieval|embedding|vector|knowledge graph)\b|知识库|检索|向量"),
        ("AI 设计", r"\b(design|figma|prototype|ui|ux)\b|设计|原型"),
        ("学习教程", r"\b(course|tutorial|learning|from scratch|guide)\b|教程|课程|学习"),
        ("Agent 工具", r"\b(agent|agents|agentic|mcp|workflow|automation|skill)\b|智能体|自动化"),
        ("模型训练/推理", r"\b(training|fine-tuning|inference|quantization|model)\b|训练|推理|量化"),
    ]
    for category, pattern in primary_checks:
        if re.search(pattern, base, flags=re.IGNORECASE):
            return category

    document_pattern = r"\b(markitdown|file conversion|convert.+markdown|pdf.+markdown|office.+markdown)\b|文档转换|格式转换"
    if re.search(document_pattern, base, flags=re.IGNORECASE) or re.search(document_pattern, readme, flags=re.IGNORECASE):
        return "文档转换"

    secondary_checks = [
        ("AI 视频生产", r"\b(video-production|text-to-video|ffmpeg|remotion)\b|视频生产|视频生成"),
        ("网站/前端生成", r"\b(website cloner|clone-website|design tokens|shadcn/ui|next\.js)\b|网站复刻|前端重建"),
        ("联网 Agent", r"\b(web-scraper|twitter|reddit|bilibili|xiaohongshu)\b"),
        ("上下文管理", r"\b(context compression|conversation memory)\b|上下文压缩"),
        ("AI 编程工作流", r"\b(agent skills|claude-code|cursor-rules|code review|codebase)\b"),
    ]
    for category, pattern in secondary_checks:
        if re.search(pattern, readme, flags=re.IGNORECASE):
            return category
    if capabilities:
        return {
            "AI 编程与代码理解": "AI 编程工作流",
            "智能体与自动化工作流": "Agent 工具",
            "知识检索与上下文增强": "RAG/知识库",
            "多媒体生成与理解": "多模态生成",
            "模型训练与推理": "模型训练/推理",
            "计算机视觉": "视觉/OCR",
            "开发框架与 SDK": "开发框架/SDK",
        }.get(capabilities[0], CAPABILITY_TAGS.get(capabilities[0], capabilities[0]))
    return "AI 工具"


def _positioning(project_name: str, description: str, capabilities: list[str], category: str) -> str:
    category_positioning = {
        "文档转换": f"{project_name} 是面向 LLM 资料处理的文档转换工具，核心目标是「{description}」。",
        "AI 视频生产": f"{project_name} 是 AI 视频生产工具，核心目标是「{description}」。",
        "上下文管理": f"{project_name} 聚焦大模型上下文管理，主要解决「{description}」。",
        "联网 Agent": f"{project_name} 是联网信息获取工具，主要帮助 Agent 读取和搜索外部内容。",
        "视觉/OCR": f"{project_name} 面向视觉识别或 OCR 场景，核心能力是「{description}」。",
        "安全研究": f"{project_name} 面向授权安全研究和工具编排，核心能力是「{description}」。",
        "金融分析": f"{project_name} 面向金融数据分析和自动化决策辅助，核心目标是「{description}」。",
        "网站/前端生成": f"{project_name} 面向网站复刻和前端重建，核心目标是「{description}」。",
    }
    if category in category_positioning:
        return category_positioning[category]
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


def _product_view(project_name: str, description: str, capabilities: list[str], category: str) -> str:
    primary = capabilities[0]
    capability_text = "、".join(capabilities[:3])
    if category == "文档转换":
        return (
            f"从产品/应用角度看，{project_name} 的价值在于把 PDF、Office、网页或多媒体资料转成更适合 LLM 消化的文本。"
            "它适合知识库入库、资料清洗、研究整理和企业文档问答前处理。"
        )
    if category == "AI 视频生产":
        return (
            f"从产品/应用角度看，{project_name} 把脚本、素材、字幕、配音和画面生成串成视频生产流程。"
            "它适合内容团队或个人开发者验证低成本视频自动化，而不是只做单点生成。"
        )
    if category == "上下文管理":
        return (
            f"从产品/应用角度看，{project_name} 解决的是大模型上下文太长、成本太高和信息噪音过多的问题。"
            "它适合 Agent、RAG 和日志分析场景中做输入压缩与上下文治理。"
        )
    if category == "联网 Agent":
        return (
            f"从产品/应用角度看，{project_name} 让 Agent 能访问外部平台信息，适合研究、舆情、竞品和内容运营场景。"
            "采用时要重点确认平台权限、稳定性和合规边界。"
        )
    if category == "网站/前端生成":
        return (
            f"从产品/应用角度看，{project_name} 把网页观察、设计 token 提取和组件重建组织成可执行流程。"
            "它适合自有站点迁移、前端原型复刻和设计还原学习，但不应绕过版权或服务条款。"
        )
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


def _highlight(project_name: str, description: str, category: str) -> str:
    templates = {
        "文档转换": f"{project_name} 把多格式文件转成 Markdown/文本，方便接入 LLM、RAG 和资料分析流程。",
        "AI 视频生产": f"{project_name} 把 AI 编程助手扩展成视频生产工作流，适合从脚本到成片的自动化验证。",
        "上下文管理": f"{project_name} 帮 Agent 压缩上下文和工具输出，降低 token 成本并保留关键信息。",
        "联网 Agent": f"{project_name} 为 Agent 接入网页和社媒信息源，让研究和监测流程更自动化。",
        "视觉/OCR": f"{project_name} 聚焦视觉识别/OCR 能力，适合把图片或文档中的信息转成可处理文本。",
        "安全研究": f"{project_name} 把安全研究工具链和知识库组织成 Agent 可调用的工作流。",
        "金融分析": f"{project_name} 用 LLM 串联行情、新闻和看板，适合验证投研分析自动化。",
        "网站/前端生成": f"{project_name} 用 AI agent 复刻网站结构和视觉细节，适合迁移自有站点或学习前端实现。",
        "AI 编程工作流": f"{project_name} 面向 AI 编程工作流，帮助代码代理更稳定地理解、修改或交付项目。",
        "Agent 工具": f"{project_name} 提供 Agent 工具、技能或工作流能力，适合扩展自动化任务边界。",
    }
    return templates.get(category, f"{project_name} 围绕「{description}」提供 AI 相关开源能力，适合快速评估和原型验证。")


def _target_users(category: str) -> list[str]:
    mapping = {
        "文档转换": ["知识库/RAG 开发者", "研究与资料整理用户", "企业文档系统团队"],
        "AI 视频生产": ["内容创作者", "营销/运营团队", "视频自动化开发者"],
        "上下文管理": ["Agent 开发者", "RAG 工程师", "关注 token 成本的团队"],
        "联网 Agent": ["研究型 Agent 开发者", "舆情/竞品分析团队", "内容运营团队"],
        "视觉/OCR": ["OCR 应用开发者", "文档自动化团队", "多模态产品团队"],
        "安全研究": ["安全研究员", "授权渗透测试团队", "安全工具开发者"],
        "金融分析": ["量化/投研团队", "金融数据开发者", "自动化看板用户"],
        "网站/前端生成": ["前端开发者", "设计工程师", "站点迁移团队"],
        "AI 编程工作流": ["AI 编程用户", "研发团队", "代码审查/交付负责人"],
        "Agent 工具": ["Agent 开发者", "自动化工作流团队", "AI 工具调研者"],
    }
    return mapping.get(category, ["AI 工具调研者", "开发者", "产品/技术团队"])


def _best_use_case(project_name: str, category: str, scenarios: list[str]) -> str:
    mapping = {
        "文档转换": f"把外部资料批量转成 Markdown 后进入知识库、RAG 或 LLM 分析链路。",
        "AI 视频生产": f"用 {project_name} 快速搭建从主题、脚本、素材到字幕/配音的自动化视频原型。",
        "上下文管理": f"在 Agent 或 RAG 工作流中压缩长日志、工具输出和检索片段。",
        "联网 Agent": f"让研究型 Agent 自动读取公开网页、社媒和视频平台资料并生成报告。",
        "视觉/OCR": f"把图片、扫描件或复杂版面内容转成结构化文本，供检索和分析使用。",
        "安全研究": f"在授权环境中组织逆向、安全测试和工具路由流程。",
        "金融分析": f"自动汇总行情、新闻和指标，生成可复核的日常投研看板。",
        "网站/前端生成": f"把自有或授权网站迁移到现代前端栈，并保留主要视觉和交互细节。",
    }
    return mapping.get(category, scenarios[0] if scenarios else "先搭建最小原型，验证它是否适配当前工作流。")


def _not_suitable(category: str, difficulty: str) -> str:
    if category == "安全研究":
        return "不适合未授权测试、灰色用途或缺少审计边界的生产环境。"
    if category in {"联网 Agent", "金融分析"}:
        return "不适合在未确认数据来源、平台条款和合规要求前直接自动化生产决策。"
    if category == "网站/前端生成":
        return "不适合用于仿冒、钓鱼、侵权复刻或未经授权复制他人品牌资产。"
    if difficulty == "高":
        return "不适合缺少运维、安全和依赖治理能力的团队直接投入生产。"
    if category == "AI 视频生产":
        return "不适合对成片质量、版权素材和品牌一致性要求很高但没有人工审核的场景。"
    return "不适合在未验证安装成本、许可证和维护活跃度前直接作为核心依赖。"


def _technical_view(
    item: RawRepo,
    text: str,
    language: str,
    capabilities: list[str],
    difficulty: str,
    category: str,
) -> str:
    capability_text = "、".join(capabilities[:3])
    stack_signals = _stack_signals(item, text)
    category_focus = {
        "文档转换": "重点应关注格式覆盖、解析保真度、批处理能力和对下游 RAG/LLM 的文本质量。",
        "AI 视频生产": "重点应关注生成链路编排、素材依赖、渲染性能、版权控制和人工审核接口。",
        "联网 Agent": "重点应关注平台适配、限流处理、失败重试、数据合规和结果可追溯性。",
        "安全研究": "重点应关注授权边界、命令执行隔离、日志审计和工具链可控性。",
        "金融分析": "重点应关注数据源可靠性、时效性、指标计算透明度和结论可复核性。",
        "视觉/OCR": "重点应关注识别准确率、版面保留、批处理性能和多语言/复杂文档支持。",
        "网站/前端生成": "重点应关注页面解析、组件还原、样式一致性和生成代码的可维护性。",
    }.get(category, f"README 和 topics 暗示其核心能力集中在{capability_text}。")
    return (
        f"技术选型上，它主要以 {language} 实现，{stack_signals}。"
        f"{category_focus}"
        f"当前接入难度评估为「{difficulty}」，建议先检查安装方式、依赖服务、示例完整度和许可证。"
    )


def _trend_view(item: RawRepo, capabilities: list[str], category: str) -> str:
    primary = capabilities[0]
    capability_text = "、".join(capabilities[:3])
    category_trends = {
        "文档转换": "LLM 应用越来越需要稳定的数据入口，文档转换正在成为 RAG 和知识库建设的前置基础设施",
        "AI 视频生产": "内容生产正在从单点生成转向脚本、素材、配音和渲染的端到端工作流",
        "联网 Agent": "Agent 的价值正在从离线推理扩展到可验证的公开信息获取和任务执行",
        "安全研究": "安全工具也在尝试用 Agent 化方式组织工具链、知识库和重复性分析流程",
        "金融分析": "投研场景正在用 LLM 连接行情、新闻和结构化指标，但可复核性比生成速度更关键",
        "视觉/OCR": "多模态应用正在从图像理解走向文档、票据和复杂版面的结构化处理",
        "网站/前端生成": "前端生产力工具正在把页面理解、设计还原和代码生成合并到一个流程中",
    }
    capability_trends = {
        "智能体与自动化工作流": "智能体正在从演示走向可执行工作流",
        "知识检索与上下文增强": "RAG 和向量检索仍是企业落地大模型的基础设施入口",
        "AI 编程与代码理解": "AI 编程工具正在从补全走向代码库级理解和审查",
        "多媒体生成与理解": "多模态能力正在进入内容生产和素材处理链路",
        "模型训练与推理": "模型推理、量化和训练工具仍在快速工程化",
    }
    trend_hint = category_trends.get(category, capability_trends.get(primary, f"社区正在关注{capability_text}方向"))
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
