# -*- coding: utf-8 -*-
"""童趣对话引擎（策略对象）。

把「说什么」与「什么时候说、状态怎么变」彻底分开：
    * 本类只负责把模板渲染成给孩子看的话，并统一过安全过滤器；
    * 什么时候调用哪个方法，由 ``states`` 里的状态处理器决定。
"""
from __future__ import annotations

import random
from typing import List, Optional

from .. import config, safety
from ..domain.question import Question
from .templates import PRAISE_BY_SUBJECT, PRAISE_POOL, TEMPLATES


class DialogueEngine:
    """面向孩子的对话引擎。"""

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()

    # ------------------------------------------------------------ 基础
    def say(self, key: str, **kwargs) -> str:
        """取模板 → 填变量 → 安全过滤。"""
        variants = TEMPLATES.get(key)
        if not variants:
            return safety.sanitize_child_text(f"[缺失话术:{key}]")
        template = self.rng.choice(list(variants))
        try:
            text = template.format(**kwargs)
        except (KeyError, IndexError):
            text = template
        return safety.sanitize_child_text(text)

    def praise(self, subject: str = "") -> str:
        """按科目挑选具体化表扬（70% 用科目池，30% 用通用池）。"""
        pool = PRAISE_BY_SUBJECT.get(subject or "")
        if pool and self.rng.random() < 0.7:
            return self.rng.choice(list(pool))
        return self.rng.choice(list(PRAISE_POOL))

    # ------------------------------------------------------------ 组合话术
    def welcome(self, child_name: str = "小朋友") -> str:
        return self.say("welcome")

    def menu(self) -> str:
        return self.say("menu")

    def subject_intro(self, subject: str) -> str:
        meta = config.SUBJECT_META[subject]
        return self.say("subject_intro", emoji=meta["emoji"], intro=meta["child_intro"])

    def question_text(self, question: Question, index: int, total: int) -> str:
        head = self.say("ask", index=index, total=total, stem=question.stem)
        body = question.display()
        extra = "\n".join(line for line in body.split("\n")[1:])
        return f"{head}\n{extra}".strip() if extra else head

    def feedback(self, question: Question, correct: bool, graded: bool, level: int) -> str:
        """统一反馈入口：答错不否定，只引导。"""
        if not graded:
            if question.kind in ("read", "speak"):
                return self.say("read_done")
            if question.kind == "open":
                return self.say("open_done")
            if correct:
                return self.say("check_done", cheer="做到啦，你真棒！" + config.STAR_EMOJI)
            return self.say("check_later", cheer="我们下次一起做，好不好呀？")
        if correct:
            key = "correct_hard" if level >= 3 else "correct"
            return self.say(key, praise=self.praise(question.subject))
        return self.say("hint", hint=question.hint or "我们一起再数一数～")

    def hint(self, question: Question) -> str:
        return self.say("hint", hint=question.hint or "我们一起再数一数～")

    def reveal_answer(self, question: Question) -> str:
        """第二次仍然不会时，温柔给出答案（绝不否定）。"""
        explanation = question.explanation or "我们一起再学一次就好啦～"
        return self.say("hint_again_soft", answer=question.answer or "我们一起读一读",
                        explanation=explanation)

    def star_award(self, tasks: int, total_stars: int) -> str:
        return self.say("star", n=tasks, star=config.STAR_EMOJI, total=total_stars)

    def rest_reminder(self, minutes: float) -> str:
        return self.say("rest", minutes=int(minutes), hint=self.rng.choice(config.REST_HINTS))

    def session_summary(self, data: dict) -> str:
        """结束语：只说做得好的地方，不批评。"""
        parts: List[str] = [f"今天我们学了大约 {data.get('minutes', 0):.0f} 分钟哦～"]
        if data.get("graded_total"):
            if data.get("accuracy", 0.0) >= 0.6:
                parts.append(f"一起玩了 {data['tasks']} 个小任务，"
                             f"答对 {data['correct']} 个，好厉害！")
            else:
                parts.append(f"一起玩了 {data['tasks']} 个小任务，动了好多小脑筋～")
        else:
            parts.append(f"一起完成了 {data.get('tasks', 0)} 个小任务～")
        if data.get("stars_earned"):
            parts.append(f"今天得到 {data['stars_earned']} 颗小星星 "
                         f"{config.STAR_EMOJI * min(int(data['stars_earned']), 5)}")
        if data.get("habits_done"):
            parts.append(f"还打卡了 {data['habits_done']} 个学习习惯，真会照顾自己！")
        if data.get("hard_topics"):
            labels = "」「".join(data["hard_topics"][:2])
            parts.append(f"今天我们多见了几次「{labels}」，明天再见一次就记住啦～")
        return self.say("ending", today="\n".join(parts))
