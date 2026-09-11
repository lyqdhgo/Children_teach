# -*- coding: utf-8 -*-
"""一次学习单元（Session）：时长、任务计数、正确率与需关注记录。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from .. import config


@dataclass
class Session:
    """一次 8~10 分钟学习单元的运行数据（实体，有生命周期）。"""

    session_id: str
    started_at: datetime
    answers: List[Dict[str, Any]] = field(default_factory=list)
    tasks: int = 0                 # 完成的小任务数（含朗读 / 习惯自查）
    graded: int = 0                # 计分题数
    correct: int = 0
    stars: int = 0
    subjects: List[str] = field(default_factory=list)
    watchlist: List[Dict[str, Any]] = field(default_factory=list)
    rounds: int = 0
    end_reason: str = ""

    # ------------------------------------------------------------ 时间
    def minutes(self, now: datetime) -> float:
        return max(0.0, (now - self.started_at).total_seconds() / 60.0)

    # ------------------------------------------------------------ 统计
    @property
    def accuracy(self) -> float:
        return (self.correct / self.graded) if self.graded else 0.0

    @property
    def assisted(self) -> int:
        """提示后被做出来的题数（家长报告里单独说明，不假装全对）。"""
        return sum(1 for row in self.answers if row.get("assisted"))

    @property
    def habit_checks(self) -> int:
        return sum(1 for row in self.answers if row["subject"] == config.SUBJECT_HABIT)

    @property
    def questions_answered(self) -> int:
        """真正完成的学习任务数（不含习惯打卡）。"""
        return len(self.answers) - self.habit_checks

    # ------------------------------------------------------------ 变更
    def start_subject(self, subject: str) -> None:
        if subject not in self.subjects:
            self.subjects.append(subject)

    def add_answer(self, row: Dict[str, Any], graded: bool, correct: bool) -> None:
        """记录一次作答并同步计数（一题只调用一次）。"""
        self.answers.append(row)
        self.tasks += 1
        if graded:
            self.graded += 1
            if correct:
                self.correct += 1

    def add_watch_item(self, item: Dict[str, Any]) -> None:
        self.watchlist.append(item)

    def summary(self) -> Dict[str, Any]:
        """交给对话引擎做「今日收获」总结的数据。"""
        return {
            "tasks": self.tasks,
            "graded_total": self.graded,
            "correct": self.correct,
            "accuracy": round(self.accuracy, 2),
            "stars_earned": self.stars,
        }
