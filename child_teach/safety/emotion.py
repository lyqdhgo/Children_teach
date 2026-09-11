# -*- coding: utf-8 -*-
"""情绪识别：抵触 / 求助 / 敏感 三类信号。

判定顺序很关键：
    * 敏感内容优先级最高（需转交家长）；
    * 「我不会」是求助，不是抵触 —— 要给提示而不是换话题；
    * 只有真正的抵触（不想学、讨厌、累了）才允许停止出题。
"""
from __future__ import annotations

from typing import Optional

from .. import config

#: 求助信号（需要引导，不算抵触）
HELP_WORDS = ("不会", "好难", "太难", "不懂", "不明白", "不知道", "怎么算", "怎么做")


def detect_emotion(text: str) -> Optional[str]:
    """返回 ``"sensitive"`` / ``"resistance"`` / ``None``。"""
    raw = (text or "").strip()
    if not raw:
        return None
    for word in config.SENSITIVE_WORDS:
        if word in raw:
            return "sensitive"
    for word in config.RESISTANCE_WORDS:
        if word in raw:
            return "resistance"
    return None


def is_help_request(text: str) -> bool:
    """孩子说「我不会」时是求助，需要启发式提示。"""
    raw = (text or "").strip()
    return any(word in raw for word in HELP_WORDS)


def looks_like_tired(consecutive_wrong: int, minutes: float) -> bool:
    """疲劳判定：连续多次答错 或 时长接近上限。"""
    return consecutive_wrong >= config.FATIGUE_WRONG_LIMIT or minutes >= config.SOFT_REST_MINUTES


def must_rest(minutes: float) -> bool:
    """硬性疲劳判定：累计满 10 分钟必须休息。"""
    return minutes >= config.HARD_REST_MINUTES
