# -*- coding: utf-8 -*-
"""领域层：与框架无关的业务对象（题目、作答轮次、学习单元、习惯项）。

这一层只依赖 ``config``，不依赖存储、HTTP、对话引擎，
因此可以被任意上层（CLI / Web / 语音）复用。
"""
from .question import (CHECK_KIND, OPEN_KINDS, Question, first_int, loose_key)
from .round import Round
from .session import Session
from .habit import DAY_GOAL_ITEMS, HABIT_ITEMS, ITEMS_BY_KEY, HabitItem

__all__ = [
    "Question", "OPEN_KINDS", "CHECK_KIND", "loose_key", "first_int",
    "Round", "Session",
    "HabitItem", "HABIT_ITEMS", "ITEMS_BY_KEY", "DAY_GOAL_ITEMS",
]
