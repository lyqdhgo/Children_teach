# -*- coding: utf-8 -*-
"""语言安全：禁用惩罚性 / 比较式 / 否定式表达。

两层防护：
    1. 上线前审计所有话术模板（``audit_dialogue_templates``）；
    2. 出口前兜底替换（``sanitize_child_text``）——即使接了大模型也不会说错话。
"""
from __future__ import annotations

from typing import List, Tuple

from .. import config


# --------------------------------------------------------------------------- #
# 孩子侧
# --------------------------------------------------------------------------- #
def check_child_text(text: str) -> List[str]:
    """检查面向孩子的话术是否触碰红线。"""
    hits = [phrase for phrase in config.BANNED_CHILD_PHRASES if phrase in (text or "")]
    return [f"出现禁止话术「{hit}」" for hit in hits]


def sanitize_child_text(text: str) -> str:
    """兜底过滤器：命中红线先替换成温和表达，仍不干净则整句替换。"""
    if not text:
        return ""
    for bad, soft in config.SOFT_REPLACEMENTS.items():
        text = text.replace(bad, soft)
    if check_child_text(text):
        return "我们再一起看看哦，慢慢来就好～"
    return text


def audit_dialogue_templates(templates) -> List[Tuple[str, List[str]]]:
    """递归审计所有童趣话术模板（支持嵌套 dict / list）。"""
    problems: List[Tuple[str, List[str]]] = []

    def walk(node, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}/{key}")
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        elif isinstance(node, str):
            hits = check_child_text(node)
            if hits:
                problems.append((path, hits))

    walk(templates, "")
    return problems


# --------------------------------------------------------------------------- #
# 家长侧（不得排名、比较、贴标签、做诊断）
# --------------------------------------------------------------------------- #
PARENT_BANNED = ("最差", "倒数", "排名第", "不如别人", "比别人", "笨", "智力",
                 "多动症", "自闭")


def check_parent_text(text: str) -> List[str]:
    hits = [phrase for phrase in PARENT_BANNED if phrase in (text or "")]
    return [f"家长报告出现不当表述「{hit}」" for hit in hits]


def sanitize_parent_text(text: str) -> str:
    if not text:
        return ""
    for bad in PARENT_BANNED:
        text = text.replace(bad, "（略）")
    return text
