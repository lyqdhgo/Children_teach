# -*- coding: utf-8 -*-
"""家长问答服务：只答事实、不超过 3 句、不比较、不做诊断。

路由用「关键词 → 处理器」表驱动（新增问法只要加一行），
比长串 if/elif 更好扩展，也更容易被审计。
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from .. import config, safety
from ..domain.habit import ITEMS_BY_KEY
from ..infra import ChildDataStore
from .aggregator import DailySummaryAggregator, WeeklySummaryAggregator
from .renderers import DailyReportRenderer, WeeklyReportRenderer

#: 家长问句 → 意图 的关键词表
ROUTES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("week", ("周报", "这周", "本周", "一周", "7天")),
    ("duration", ("多久", "时长", "多长时间", "时间")),
    ("accuracy", ("正确率", "对不对", "表现", "答对", "水平")),
    ("content", ("学了什么", "内容", "科目", "今天")),
    ("stars", ("星星", "奖励")),
    ("habit", ("习惯", "打卡", "坐姿", "整理", "阅读")),
    ("level", ("难度", "简单", "太难", "进度")),
    ("watch", ("敏感", "情绪", "不开心", "关注")),
    ("advice", ("建议", "怎么办", "怎么帮")),
)


class ParentQAService:
    """家长侧问答：简洁、客观、只回答数据问题。"""

    def __init__(self, data_store: ChildDataStore, habit_repository) -> None:
        self.data_store = data_store
        self.habits = habit_repository
        self.daily = DailySummaryAggregator(data_store, habit_repository)
        self.weekly = WeeklySummaryAggregator(data_store, habit_repository)
        self.daily_renderer = DailyReportRenderer()
        self.weekly_renderer = WeeklyReportRenderer()
        self._handlers: Dict[str, Callable[[dict, str], str]] = {
            "week": self._week,
            "duration": self._duration,
            "accuracy": self._accuracy,
            "content": self._content,
            "stars": self._stars,
            "habit": self._habit,
            "level": self._level,
            "watch": self._watch,
            "advice": self._advice,
        }

    # ------------------------------------------------------------ 对外
    def answer(self, query: str, day: Optional[str] = None) -> str:
        summary = self.daily.build(day)
        question = (query or "").strip()
        if not question:
            return self.daily_renderer.render(summary)

        intent = self.classify(question)
        if intent is None:
            return self.daily_renderer.render(summary)
        return safety.sanitize_parent_text(self._handlers[intent](summary, question))

    @staticmethod
    def classify(question: str) -> Optional[str]:
        """识别家长问句意图（表驱动，顺序即优先级）。"""
        for intent, keywords in ROUTES:
            if any(keyword in question for keyword in keywords):
                return intent
        return None

    # ------------------------------------------------------------ 各意图回答
    def _week(self, summary: dict, question: str) -> str:
        return self.weekly_renderer.render(self.weekly.build(summary["day"]))

    @staticmethod
    def _duration(summary: dict, question: str) -> str:
        if summary["sessions"] == 0:
            return "今日暂无学习时长记录。"
        return (f"今日累计学习 {summary['minutes']} 分钟，"
                f"分 {summary['sessions']} 次完成，单次均在 10 分钟以内。")

    @staticmethod
    def _accuracy(summary: dict, question: str) -> str:
        if not summary["graded"]:
            return "今日暂无计分题目，只有朗读/习惯类任务，因此没有正确率数据。"
        return (f"今日计分题 {summary['graded']} 道，正确 {summary['correct']} 道，"
                f"正确率 {int(float(summary['accuracy']) * 100)}%。")

    @staticmethod
    def _content(summary: dict, question: str) -> str:
        if summary["sessions"] == 0:
            return "今日暂无学习记录。"
        labels = "、".join(config.subject_name(s) for s in summary["subject_count"]) or "—"
        topics = "、".join(config.topic_label(str(t["subject"]), str(t["topic"]))
                          for t in summary["topics"][:3]) or "—"
        return f"今日学习科目：{labels}。练习重点：{topics}。"

    @staticmethod
    def _stars(summary: dict, question: str) -> str:
        return f"今日获得 {summary['stars']} 颗星星，累计 {summary['stars_total']} 颗。"

    @staticmethod
    def _habit(summary: dict, question: str) -> str:
        names = [ITEMS_BY_KEY[key].label for key in summary["habit_keys"]]
        done = "、".join(names) if names else "暂无"
        return (f"今日打卡 {summary['habits_done']}/{summary['habits_total']} 项：{done}。"
                f"当前连续打卡 {summary['streak']} 天。")

    @staticmethod
    def _level(summary: dict, question: str) -> str:
        if not summary["topics"]:
            return "今日暂无难度数据。"
        rows = "；".join(
            f"{config.topic_label(str(t['subject']), str(t['topic']))}"
            f"={config.LEVEL_LABELS.get(int(t['level']), t['level'])}"
            for t in summary["topics"][:3]
        )
        return f"当前难度水平：{rows}。系统按答题正确率自动调整，单次不超过 3 题。"

    @staticmethod
    def _watch(summary: dict, question: str) -> str:
        if not summary["watchlist"]:
            return "今日无异常记录。"
        return (f"今日有 {len(summary['watchlist'])} 条需关注记录"
                f"（已记录时间与内容，未做评判性处理）。建议家长温和沟通一次。")

    @staticmethod
    def _advice(summary: dict, question: str) -> str:
        return "建议：" + DailyReportRenderer.suggest(summary)


# --------------------------------------------------------------------------- #
# 便捷函数（保持函数式调用可用）
# --------------------------------------------------------------------------- #
def answer_parent_question(query: str, data_store: ChildDataStore, habits,
                           day: Optional[str] = None) -> str:
    return ParentQAService(data_store, habits).answer(query, day)


def route_table() -> List[Tuple[str, Tuple[str, ...]]]:
    """导出路由表，便于文档与调试展示。"""
    return list(ROUTES)
