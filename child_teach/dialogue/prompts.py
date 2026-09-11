# -*- coding: utf-8 -*-
"""系统提示词加载与拼装（给对话子 Agent 使用）。

提示词正文存放在 ``prompts/*.md``，本模块只负责读取、缓存与上下文拼装，
家长/老师可以直接改 Markdown 文案，不必改代码。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Optional

from .. import config

PROMPT_FILES: Dict[str, str] = {
    "child_dialogue": "child_dialogue_system_prompt.md",
    "learning_buddy": "learning_buddy_prompt.md",
    "parent_report": "parent_report_prompt.md",
}

#: 文件缺失时的最小可用兜底（保证 Agent 永远有系统提示词）
FALLBACKS: Dict[str, str] = {
    "child_dialogue": (
        "你是「小星老师」，陪 7 岁一年级小朋友学习。"
        "句子要短（≤15 字），语气温和童趣，多用鼓励和表情。"
        "一次最多 3 道题；答错不否定，换个方式启发；连续学习 10 分钟必须提醒休息；"
        "遇到抵触情绪不强迫，可切换小游戏或结束；遇到敏感问题告知家长。"
        "范围仅限：语文（拼音/生字/短句/短古诗）、数学（20 以内加减/钟表/图形）、"
        "英语（简单单词短句跟读）、学习习惯。禁止超纲、禁止惩罚性语言、禁止比较。"
    ),
    "learning_buddy": (
        "你是7岁小朋友的启蒙学习伙伴，负责语数英启蒙和学习习惯引导。"
        "语言简短亲切，一次最多3题，答错换方式启发，10分钟提醒休息，不强迫学习。"
    ),
    "parent_report": (
        "你是儿童学习数据汇报助手。面向家长，输出简洁客观的数据事实，5 行以内，"
        "不评价孩子、不比较、不排名，建议最多 1 条。"
    ),
}


@lru_cache(maxsize=8)
def load(name: str) -> str:
    """读取提示词（带缓存），文件缺失时返回兜底文案。"""
    filename = PROMPT_FILES.get(name)
    if not filename:
        raise KeyError(f"未知提示词：{name}（可选：{list(PROMPT_FILES)}）")
    path = config.PROMPT_DIR / filename
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return FALLBACKS[name]


def child_dialogue_prompt(child_name: str = "小朋友", extra: Optional[str] = None) -> str:
    """面向孩子的对话系统提示词。"""
    text = load("child_dialogue")
    text += f"\n\n## 当前小朋友\n- 称呼：{child_name}\n"
    if extra:
        text += f"\n## 运行时补充约束\n{extra}\n"
    return text


def learning_buddy_prompt(extra: Optional[str] = None) -> str:
    """配套子 Agent（学习伙伴）系统提示词。"""
    text = load("learning_buddy")
    if extra:
        text += f"\n\n补充约束：\n{extra}\n"
    return text


def parent_report_prompt(extra: Optional[str] = None) -> str:
    """面向家长的汇报系统提示词。"""
    text = load("parent_report")
    if extra:
        text += f"\n\n补充约束：\n{extra}\n"
    return text


def runtime_constraints() -> str:
    """由配置生成的硬性约束（写进提示词，保证模型与代码规则一致）。"""
    return (
        f"- 单次最多 {config.MAX_QUESTIONS_PER_ROUND} 道题；"
        f"一个学习单元累计不超过 {config.MAX_QUESTIONS_PER_SESSION} 道。\n"
        f"- 单次学习 {config.UNIT_MINUTES} 分钟，满 {config.HARD_REST_MINUTES} 分钟必须提醒休息。\n"
        f"- 每完成 {config.TASKS_PER_STAR} 个小任务给 1 颗小星星 {config.STAR_EMOJI}。\n"
        f"- 数学上限：{config.MATH_MAX_NUMBER} 以内加减，禁止乘除法与 "
        f"{config.HARD_MAX_NUMBER} 以上数字。\n"
        f"- 禁止惩罚性语言、比较式话术；答错不否定，只做启发式引导。"
    )


def available() -> Dict[str, str]:
    """列出所有提示词名称与文件路径（供 CLI 查看）。"""
    return {name: str(config.PROMPT_DIR / fname) for name, fname in PROMPT_FILES.items()}
