# -*- coding: utf-8 -*-
"""安全边界：题库超纲审计。

把「禁止超纲」写成可执行断言：任何题目入库前都要过这里，
不合规直接拒绝，而不是靠人去记住规则。
"""
from __future__ import annotations

import re
from typing import Iterable, List, Tuple

from .. import config

_NUMBER_RE = re.compile(r"\d+")
#: 英文语法类关键词（英语题不得涉及）
_EN_GRAMMAR_RE = re.compile(
    r"\b(tense|grammar|plural|past tense|present perfect|passive|phonetic|"
    r"sentence pattern|clause)\b",
    re.IGNORECASE,
)


def extract_numbers(text: str) -> List[int]:
    """取出文本中的整数（用于判断是否超出该知识点的数字上限）。"""
    return [int(m) for m in _NUMBER_RE.findall(text or "")]


def check_question(question) -> List[str]:
    """检查单道题是否违反安全边界，返回问题列表（空 = 通过）。

    参数用鸭子类型，避免与领域层互相依赖。
    """
    issues: List[str] = []
    subject = getattr(question, "subject", "")
    topic = getattr(question, "topic", "")
    kind = getattr(question, "kind", "choice")
    stem = getattr(question, "stem", "") or ""
    answer = getattr(question, "answer", "") or ""
    options = list(getattr(question, "options", ()) or ())

    # 1.1 难度必须在允许区间
    difficulty = getattr(question, "difficulty", 0)
    if not (config.MIN_DIFFICULTY <= int(difficulty) <= config.MAX_DIFFICULTY):
        issues.append(f"难度 {difficulty} 超出 {config.GRADE} 年级允许区间")

    # 1.2 题干过长（孩子注意力与识字量有限）
    if len(stem) > config.MAX_STEM_CHARS:
        issues.append(f"题干 {len(stem)} 字，超过 {config.MAX_STEM_CHARS} 字上限")

    # 1.3 选项过多
    if len(options) > config.MAX_OPTIONS:
        issues.append(f"选项 {len(options)} 个，超过 {config.MAX_OPTIONS} 个上限")

    # 1.4 超纲关键词（乘除法、复杂语法等）
    haystack = " ".join([stem, answer, " ".join(options)])
    for keyword in config.OUT_OF_SCOPE_KEYWORDS:
        if keyword in haystack:
            issues.append(f"出现超纲关键词「{keyword}」")
    if _EN_GRAMMAR_RE.search(haystack):
        issues.append("英语题涉及语法讲解，超出低幼启蒙范围")

    # 1.5 数字范围（任何题目不得出现 100 以上数字）
    limit = min(config.topic_limit(subject, topic), config.HARD_MAX_NUMBER)
    for number in extract_numbers(haystack):
        if number > limit:
            issues.append(f"出现数字 {number}，超过该知识点上限 {limit}（禁止超纲）")

    # 1.6 英语题不得要求拼写长单词
    if subject == config.SUBJECT_ENGLISH:
        for word in re.findall(r"[A-Za-z]{9,}", haystack):
            issues.append(f"英文单词「{word}」过长，不适合 7 岁跟读")

    # 1.7 选择题必须有答案且答案在选项中
    if kind == "choice":
        if not options:
            issues.append("选择题没有选项")
        if not answer:
            issues.append("选择题没有答案")
        elif answer not in options:
            issues.append("选择题答案不在选项中")

    # 1.8 每题必须带启发式提示（答错时不能直接否定）
    if not (getattr(question, "hint", "") or "").strip():
        issues.append("缺少启发式提示 hint（答错时需要引导而不是否定）")

    return issues


def audit_bank(questions: Iterable) -> Tuple[List[Tuple[str, List[str]]], int]:
    """审计整个题库，返回 (问题清单, 题目总数)。"""
    problems: List[Tuple[str, List[str]]] = []
    total = 0
    for question in questions:
        total += 1
        issues = check_question(question)
        if issues:
            problems.append((getattr(question, "qid", "?"), issues))
    return problems, total
