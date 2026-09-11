# -*- coding: utf-8 -*-
"""数据聚合器：把学习记录流水 + 打卡日志汇总成结构化数据。

只做「算数据」，不做「写文案」（那是 renderers 的职责），
也不做「问答路由」（那是 qa 的职责）。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .. import config
from ..infra import ChildDataStore, today_str


def accuracy_of(correct: int, total: int) -> float:
    return round(correct / total, 2) if total else 0.0


class DailySummaryAggregator:
    """汇总某一天的学习与习惯数据（纯数据，不做评价）。"""

    def __init__(self, data_store: ChildDataStore, habit_repository) -> None:
        self.data_store = data_store
        self.habits = habit_repository

    def build(self, day: Optional[str] = None) -> Dict[str, object]:
        day = day or today_str()
        sessions = self.data_store.history.sessions_on(day)

        minutes = round(sum(float(s.get("minutes", 0)) for s in sessions), 1)
        questions = sum(int(s.get("questions_answered", s.get("questions_total", 0)))
                        for s in sessions)
        graded = sum(int(s.get("graded_total", 0)) for s in sessions)
        correct = sum(int(s.get("correct", 0)) for s in sessions)
        assisted = sum(int(s.get("assisted", 0)) for s in sessions)
        stars = sum(int(s.get("stars_earned", 0)) for s in sessions)

        subject_count: Dict[str, int] = {}
        topic_rows: Dict[str, dict] = {}
        watchlist: List[dict] = []
        for session in sessions:
            for subject in session.get("subjects", []):
                subject_count[subject] = subject_count.get(subject, 0) + 1
            for row in session.get("topics", []):
                key = f"{row['subject']}/{row['topic']}"
                item = topic_rows.setdefault(key, {
                    "subject": row["subject"], "topic": row["topic"],
                    "attempts": 0, "correct": 0, "level": row.get("level", 1),
                })
                item["attempts"] += int(row.get("attempts", 0))
                item["correct"] += int(row.get("correct", 0))
                item["level"] = max(item["level"], int(row.get("level", 1)))
            watchlist.extend(session.get("watchlist", []))

        habit_progress = self.habits.progress(day)
        return {
            "day": day,
            "sessions": len(sessions),
            "minutes": minutes,
            "questions": questions,
            "graded": graded,
            "correct": correct,
            "assisted": assisted,
            "accuracy": accuracy_of(correct, graded),
            "stars": stars,
            "subject_count": subject_count,
            "topics": list(topic_rows.values()),
            "habits_done": habit_progress["done"],
            "habits_total": habit_progress["total"],
            "habit_keys": habit_progress["done_keys"],
            "habit_goal": self.habits.goal(day),
            "streak": self.habits.streak(day),
            "watchlist": watchlist,
            "stars_total": self.data_store.profile.stars_total,
        }


class WeeklySummaryAggregator:
    """汇总最近 7 天的学习与习惯数据。"""

    def __init__(self, data_store: ChildDataStore, habit_repository) -> None:
        self.data_store = data_store
        self.habits = habit_repository

    def build(self, end_day: Optional[str] = None) -> Dict[str, object]:
        end_day = end_day or today_str()
        end = datetime.strptime(end_day, "%Y-%m-%d").date()
        start_day = (end - timedelta(days=6)).strftime("%Y-%m-%d")
        sessions = self.data_store.history.sessions_between(start_day, end_day)

        graded = sum(int(s.get("graded_total", 0)) for s in sessions)
        correct = sum(int(s.get("correct", 0)) for s in sessions)
        by_subject: Dict[str, int] = {}
        for session in sessions:
            for subject in session.get("subjects", []):
                by_subject[subject] = by_subject.get(subject, 0) + 1

        return {
            "start": start_day,
            "end": end_day,
            "study_days": len({s.get("date") for s in sessions}),
            "sessions": len(sessions),
            "minutes": round(sum(float(s.get("minutes", 0)) for s in sessions), 1),
            "questions": sum(int(s.get("questions_answered", s.get("questions_total", 0)))
                             for s in sessions),
            "graded": graded,
            "correct": correct,
            "accuracy": accuracy_of(correct, graded),
            "stars": sum(int(s.get("stars_earned", 0)) for s in sessions),
            "by_subject": by_subject,
            "habits": self.habits.weekly_report(end_day),
            "mastered_topics": self.mastered_topics(),
        }

    def mastered_topics(self) -> List[dict]:
        """已掌握的知识点（供周报使用）。"""
        rows = []
        for key, stat in (self.data_store.profile.topics or {}).items():
            if stat.get("mastered"):
                subject, _, topic = key.partition("/")
                rows.append({"subject": subject, "topic": topic})
        return rows


# --------------------------------------------------------------------------- #
# 便捷函数（保持函数式调用可用）
# --------------------------------------------------------------------------- #
def build_daily_summary(data_store: ChildDataStore, habits, day: Optional[str] = None) -> dict:
    return DailySummaryAggregator(data_store, habits).build(day)


def build_weekly_report(data_store: ChildDataStore, habits, day: Optional[str] = None) -> dict:
    return WeeklySummaryAggregator(data_store, habits).build(day)


def subject_names(subject_count: Dict[str, int]) -> str:
    """科目分布文案（如「数学启蒙、语文启蒙」）。"""
    return "、".join(config.subject_name(s) for s in subject_count if s in config.SUBJECT_META)
