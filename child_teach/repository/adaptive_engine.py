# -*- coding: utf-8 -*-
"""自适应难度引擎（策略对象）。

职责（对应需求「难度自适应」）：
    1. 记录每个知识点的答题正确率（滚动窗口）
    2. 动态升降难度：连续答对 → 升级；连续答错 → 降级
    3. 掌握度判定：稳定答对的知识点标记为「已掌握」
    4. 选题策略：优先新题 / 曾做错题，不再大量重复已掌握的题

依赖的是 ``ProfileRepository`` 与 ``QuestionRepository`` 两个抽象，
本身不接触文件路径，也不接触对话与状态机。
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence

from .. import config
from ..domain.question import OPEN_KINDS, Question
from ..infra import ProfileRepository, now_iso
from .question_repository import QuestionRepository

RECENT_WINDOW = 5          # 滚动窗口大小
LEVEL_UP_MIN_SAMPLES = 4   # 升级前至少作答次数
LEVEL_UP_RATE = 0.75       # 最近 4 次正确率 ≥ 75% → 升级
LEVEL_DOWN_RATE = 0.5      # 最近 4 次正确率 ≤ 50% → 降级
MASTER_ATTEMPTS = 4        # 掌握度：最少作答次数
MASTER_RATE = 0.8          # 掌握度：正确率阈值

LEVEL_LABELS = {1: "基础", 2: "巩固", 3: "挑战"}

#: 选题权重：越大越优先
WEIGHT_NEW = 3.0           # 从没做过
WEIGHT_WRONG_ONLY = 4.0    # 错过还没对过
WEIGHT_MIXED = 2.0         # 对过也错过
WEIGHT_MASTERED = 0.6      # 一直答对，减少重复


class AdaptiveEngine:
    """按知识点维护难度与掌握度，并据此选题。"""

    def __init__(self, profile: ProfileRepository, repository: QuestionRepository) -> None:
        self.profile = profile
        self.repository = repository

    # ------------------------------------------------------------ 工具
    @staticmethod
    def key(subject: str, topic: str) -> str:
        return f"{subject}/{topic}"

    def topic_stat(self, subject: str, topic: str) -> dict:
        """返回（并初始化）某个知识点的统计对象。"""
        stat = self.profile.topics.setdefault(
            self.key(subject, topic),
            {"attempts": 0, "correct": 0, "recent": [], "level": config.START_DIFFICULTY,
             "mastered": False, "updated_at": now_iso()},
        )
        stat.setdefault("recent", [])
        stat.setdefault("level", config.START_DIFFICULTY)
        stat.setdefault("mastered", False)
        return stat

    # ------------------------------------------------------------ 查询
    def level_for(self, subject: str, topic: str) -> int:
        level = int(self.topic_stat(subject, topic).get("level", config.START_DIFFICULTY))
        cap = self.profile.difficulty_cap(config.MAX_DIFFICULTY)
        return max(config.MIN_DIFFICULTY, min(level, cap, config.MAX_DIFFICULTY))

    def is_mastered(self, subject: str, topic: str) -> bool:
        return bool(self.topic_stat(subject, topic).get("mastered"))

    def accuracy(self, subject: Optional[str] = None, topic: Optional[str] = None) -> float:
        """正确率（0~1）；不传参数则统计全部知识点。"""
        attempts = correct = 0
        for key, stat in self.profile.topics.items():
            sub, _, top = key.partition("/")
            if subject and sub != subject:
                continue
            if topic and top != topic:
                continue
            attempts += int(stat.get("attempts", 0))
            correct += int(stat.get("correct", 0))
        return (correct / attempts) if attempts else 0.0

    def stats_snapshot(self) -> List[dict]:
        """按知识点汇总，供家长报告使用。"""
        rows = []
        for key, stat in sorted(self.profile.topics.items()):
            attempts = int(stat.get("attempts", 0))
            if attempts == 0:
                continue
            subject, _, topic = key.partition("/")
            rows.append({
                "subject": subject,
                "topic": topic,
                "attempts": attempts,
                "correct": int(stat.get("correct", 0)),
                "accuracy": round(int(stat.get("correct", 0)) / attempts, 2),
                "level": int(stat.get("level", 1)),
                "mastered": bool(stat.get("mastered", False)),
            })
        return rows

    def level_label(self, subject: str, topic: str) -> str:
        return LEVEL_LABELS.get(self.level_for(subject, topic), "基础")

    # ------------------------------------------------------------ 记录作答
    def record_answer(self, question: Question, correct: bool, graded: bool = True) -> dict:
        """记录一次作答并更新难度。

        返回 ``{"level_changed": -1/0/1, "level": n, "just_mastered": bool}``
        """
        if not graded:
            # 朗读 / 看图说话 / 习惯自查不参与难度计算
            return {"level_changed": 0,
                    "level": self.level_for(question.subject, question.topic),
                    "just_mastered": False}

        stat = self.topic_stat(question.subject, question.topic)
        stat["attempts"] = int(stat.get("attempts", 0)) + 1
        if correct:
            stat["correct"] = int(stat.get("correct", 0)) + 1
        recent = list(stat.get("recent", []))
        recent.append(1 if correct else 0)
        stat["recent"] = recent[-RECENT_WINDOW:]
        stat["updated_at"] = now_iso()

        # ---- 动态升降难度 ----
        old_level = int(stat.get("level", config.START_DIFFICULTY))
        window = stat["recent"][-LEVEL_UP_MIN_SAMPLES:]
        rate = sum(window) / len(window) if window else 0.0
        new_level = old_level
        if len(window) >= LEVEL_UP_MIN_SAMPLES and rate >= LEVEL_UP_RATE:
            new_level = min(old_level + 1, config.MAX_DIFFICULTY)
        elif len(window) >= LEVEL_UP_MIN_SAMPLES and rate <= LEVEL_DOWN_RATE:
            new_level = max(old_level - 1, config.MIN_DIFFICULTY)
        stat["level"] = new_level

        # ---- 掌握度判定（会回落）----
        attempts = int(stat["attempts"])
        rate_total = int(stat["correct"]) / attempts
        just_mastered = False
        if attempts >= MASTER_ATTEMPTS and rate_total >= MASTER_RATE and not stat.get("mastered"):
            stat["mastered"] = True
            just_mastered = True
        elif stat.get("mastered") and rate_total < LEVEL_DOWN_RATE and attempts >= MASTER_ATTEMPTS:
            stat["mastered"] = False

        self.profile.mark_seen(question.qid, correct)
        self.profile.save()
        return {"level_changed": new_level - old_level, "level": new_level,
                "just_mastered": just_mastered}

    # ------------------------------------------------------------ 选题策略
    def _weight(self, question: Question) -> float:
        """题目权重：没见过 / 曾做错 的优先，已掌握且答对的靠后。"""
        record = self.profile.seen.get(question.qid, {})
        right = int(record.get("c", 0))
        wrong = int(record.get("w", 0))
        if right + wrong == 0:
            return WEIGHT_NEW
        if wrong and not right:
            return WEIGHT_WRONG_ONLY
        if wrong:
            return WEIGHT_MIXED
        return WEIGHT_MASTERED

    def select(self, subject: str, count: int = config.MAX_QUESTIONS_PER_ROUND,
               rng: Optional[random.Random] = None) -> List[Question]:
        """为一次学习任务挑选题目（默认最多 3 题，硬性截断）。"""
        rng = rng or random.Random()
        count = min(count, config.MAX_QUESTIONS_PER_ROUND)
        pool = self.repository.by_subject(subject)
        if not pool:
            return []

        # 1) 难度窗口：按每个知识点自己的等级取题，避免整体跳跃
        def in_window(question: Question) -> bool:
            level = self.level_for(question.subject, question.topic)
            return question.difficulty in (level, max(config.MIN_DIFFICULTY, level - 1))

        # 2) 已掌握的知识点先排除（不重复大量已掌握题目）
        primary = [q for q in pool
                   if in_window(q) and not self.is_mastered(q.subject, q.topic)]
        secondary = [q for q in pool
                     if in_window(q) and self.is_mastered(q.subject, q.topic)]
        tertiary = [q for q in pool if q not in primary and q not in secondary]

        chosen: List[Question] = []
        topic_count: Dict[str, int] = {}
        open_count = 0

        def take_from(candidates: Sequence[Question]) -> None:
            nonlocal open_count
            weighted = sorted(candidates, key=self._weight, reverse=True)
            rng.shuffle(weighted)                       # 同权重内部打乱，保证新鲜感
            weighted.sort(key=self._weight, reverse=True)
            for question in weighted:
                if len(chosen) >= count:
                    return
                if question in chosen:
                    continue
                if topic_count.get(question.topic, 0) >= 2:       # 同一知识点最多 2 题
                    continue
                if question.kind in OPEN_KINDS and open_count >= 1:  # 开放题每轮最多 1 题
                    continue
                chosen.append(question)
                topic_count[question.topic] = topic_count.get(question.topic, 0) + 1
                if question.kind in OPEN_KINDS:
                    open_count += 1

        for layer in (primary, secondary, tertiary):
            if len(chosen) >= count:
                break
            take_from(layer)
        return chosen[:count]
