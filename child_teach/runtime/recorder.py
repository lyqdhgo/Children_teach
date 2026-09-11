# -*- coding: utf-8 -*-
"""学习记录生成器：把一次学习单元落成一条可追溯的 JSON 记录。"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .. import config
from ..domain.session import Session
from ..infra import ChildDataStore, now_iso, today_str


class SessionRecorder:
    """负责「生成记录」与「写入流水」，不参与任何对话逻辑。"""

    def __init__(self, data_store: ChildDataStore, adaptive) -> None:
        self.data_store = data_store
        self.adaptive = adaptive

    # ------------------------------------------------------------ 生成
    def build(self, session: Session, *, now: datetime, reason: str,
              questions_presented: int, habit_progress: Dict[str, object],
              state_trace: str) -> Dict[str, object]:
        return {
            "session_id": session.session_id,
            "date": today_str(),
            "started_at": session.started_at.replace(microsecond=0).isoformat(),
            "ended_at": now_iso(),
            "minutes": round(session.minutes(now), 1),
            "questions_total": questions_presented,        # 呈现过的题数（含未作答）
            "questions_answered": session.questions_answered,
            "tasks_total": session.tasks,
            "habit_checks": session.habit_checks,
            "graded_total": session.graded,
            "correct": session.correct,
            "assisted": session.assisted,
            "accuracy": round(session.accuracy, 2),
            "stars_earned": session.stars,
            "subjects": list(session.subjects),
            "topics": self._topic_rows(session),
            "habits_done": habit_progress["done"],
            "habit_keys": habit_progress["done_keys"],
            "rounds": session.rounds,
            "watchlist": session.watchlist,
            "answers": session.answers,
            "end_reason": reason,
            "state_trace": state_trace,
        }

    def _topic_rows(self, session: Session) -> List[dict]:
        """按知识点汇总本次的作答（家长报告与难度回溯用）。"""
        rows: Dict[Tuple[str, str], dict] = {}
        for answer in session.answers:
            key = (answer["subject"], answer["topic"])
            row = rows.setdefault(key, {
                "subject": answer["subject"], "topic": answer["topic"],
                "attempts": 0, "correct": 0,
                "level": self.adaptive.level_for(*key),
            })
            if answer["graded"]:
                row["attempts"] += 1
                row["correct"] += 1 if answer["correct"] else 0
        return list(rows.values())

    # ------------------------------------------------------------ 写入
    def save(self, record: Dict[str, object]) -> None:
        self.data_store.history.append(record)

    def record(self, session: Session, *, now: datetime, reason: str,
               questions_presented: int, habit_progress: Dict[str, object],
               state_trace: str) -> Dict[str, object]:
        """生成并落盘，返回记录本身。"""
        payload = self.build(session, now=now, reason=reason,
                             questions_presented=questions_presented,
                             habit_progress=habit_progress, state_trace=state_trace)
        self.save(payload)
        return payload


def weak_topic_labels(answers: Optional[List[dict]]) -> List[str]:
    """本次出现错误的知识点中文名（用于结束语，不出现英文标识）。"""
    labels: List[str] = []
    for answer in answers or []:
        if answer["graded"] and not answer["correct"]:
            label = config.topic_label(answer["subject"], answer["topic"])
            if label not in labels:
                labels.append(label)
    return labels
