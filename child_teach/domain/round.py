# -*- coding: utf-8 -*-
"""一组学习任务（Round）：一次最多 3 道题，自带进度与判空。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .question import Question


@dataclass
class Round:
    """一个「小任务组」：题目列表 + 当前进度。"""

    subject: str
    questions: List[Question] = field(default_factory=list)
    index: int = 0

    # ------------------------------------------------------------ 查询
    @property
    def total(self) -> int:
        return len(self.questions)

    @property
    def position(self) -> int:
        """当前第几题（1 起，用于「第 2 个小任务」这类话术）。"""
        return min(self.index + 1, max(self.total, 1))

    def current(self) -> Optional[Question]:
        if 0 <= self.index < self.total:
            return self.questions[self.index]
        return None

    def is_finished(self) -> bool:
        return self.index >= self.total

    def __len__(self) -> int:
        return self.total

    # ------------------------------------------------------------ 变更
    def advance(self) -> Optional[Question]:
        """进入下一题，返回下一题（没有则返回 None）。"""
        self.index += 1
        return self.current()
