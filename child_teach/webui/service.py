# -*- coding: utf-8 -*-
"""网页服务层：把 Agent 包装成线程安全的门面，并决定「点什么按钮就能答」。

这一层只做适配，不写业务规则：
    * 状态 → 快捷按钮（降低 7 岁孩子的打字负担）
    * Agent 结果 → 前端 JSON
    * 家长接口 → 简报 / 周报 / 问答 / 题库自检
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import config, safety
from ..agent import ChildTutorAgent
from ..dialogue.templates import TEMPLATES
from ..domain.habit import HABIT_ITEMS
from ..runtime.conversation_graph import (STATE_ANSWER, STATE_CHOOSE_SUBJECT, STATE_END,
                                          STATE_HABIT, STATE_LEARNING, STATE_REST,
                                          STATE_REWARD)

MENU_CHOICES = ["语文", "数学", "英语", "习惯小游戏"]
HABIT_ACK = ["做到啦", "还没有"]
HABIT_GOAL_SAMPLES = ["坐姿棒棒的", "自己收好文具", "读一页小书"]
HELP_CHOICE = "我不会"


class TutorService:
    """Agent 的线程安全门面（单孩子、单进程使用）。"""

    def __init__(self, data_dir: Optional[Path] = None,
                 child_name: str = "小朋友") -> None:
        self._lock = threading.RLock()
        self.child_name = child_name
        self.agent = ChildTutorAgent(data_dir=data_dir, child_name=child_name)
        self.agent.start()

    # ------------------------------------------------------------ 状态
    def status(self) -> Dict[str, Any]:
        snapshot = self.agent.status()
        snapshot["minutes"] = snapshot.get("session_minutes", 0)   # 前端字段名
        snapshot["child_name"] = self.agent.child_name
        return snapshot

    def suggestions(self, result) -> List[str]:
        """根据当前状态给出「点一下就能回答」的按钮。"""
        state = result.state
        meta = result.meta or {}
        if state == STATE_END:
            return ["开始"]
        if state == STATE_CHOOSE_SUBJECT:
            return list(MENU_CHOICES)
        if state == STATE_ANSWER:
            kind = meta.get("kind")
            if kind == "choice":
                return list(meta.get("options") or []) + [HELP_CHOICE]
            if kind in ("read", "speak"):
                return ["我读完啦", HELP_CHOICE]
            if kind == "open":
                return ["我说好啦", HELP_CHOICE]
            if kind == "check":
                return list(HABIT_ACK)
            return [HELP_CHOICE]
        if state == STATE_REWARD:
            return ["再玩一组", "换个科目", "今天到这里"]
        if state == STATE_REST:
            return ["好啦", "小游戏", "结束"]
        if state == STATE_HABIT:
            if self.agent.habit_stage == "goal":
                return list(HABIT_GOAL_SAMPLES)
            return list(HABIT_ACK)
        if state == STATE_LEARNING:
            return []
        return []

    def payload(self, result) -> Dict[str, Any]:
        meta = result.meta or {}
        return {
            "child_text": result.child_text,
            "state": result.state,
            "state_path": result.state_path,
            "parent_note": result.parent_note,
            "finished": result.finished,
            "meta": meta,
            "status": self.status(),
            "suggestions": self.suggestions(result),
            "habit_sync": bool(meta.get("habit_item") or meta.get("habit_progress")
                               or meta.get("habit_stage") or meta.get("habit_goal")),
        }

    # ------------------------------------------------------------ 学习
    def start(self) -> Dict[str, Any]:
        with self._lock:
            return self.payload(self.agent.start())

    def say(self, text: str) -> Dict[str, Any]:
        with self._lock:
            return self.payload(self.agent.handle(text))

    # ------------------------------------------------------------ 打卡
    def habit_state(self) -> Dict[str, Any]:
        with self._lock:
            progress = self.agent.habits.progress()
            items = [
                {
                    "key": item.key,
                    "label": item.label,
                    "child_prompt": item.child_prompt,
                    "done": self.agent.habits.is_done(item.key),
                }
                for item in HABIT_ITEMS
            ]
            return {
                "goal": self.agent.habits.goal(),
                "items": items,
                "progress": progress,
                "summary": self.agent.habits.child_progress_text()
                           + f"（连续 {self.agent.habits.streak()} 天）",
                "weekly": self.agent.parent_weekly(),
                "suggestions": list(HABIT_GOAL_SAMPLES),
            }

    def habit_check(self, key: str, done: bool) -> Dict[str, Any]:
        with self._lock:
            self.agent.habits.check(key, done)
            return self.habit_state()

    def habit_goal(self, goal: str) -> Dict[str, Any]:
        with self._lock:
            self.agent.habits.set_goal(goal)
            return self.habit_state()

    # ------------------------------------------------------------ 家长
    def parent_summary(self) -> str:
        with self._lock:
            return self.agent.parent_summary()

    def parent_week(self) -> str:
        with self._lock:
            return self.agent.parent_weekly()

    def parent_advice(self) -> str:
        with self._lock:
            return self.agent.parent_ask("建议")

    def parent_ask(self, query: str) -> str:
        with self._lock:
            return self.agent.parent_ask(query)

    # ------------------------------------------------------------ 自检与架构
    def bank_report(self) -> str:
        """题库统计 + 安全审计结果（页面「安全边界」卡片）。"""
        with self._lock:
            problems, total = self.agent.bank.audit()
        lines = [f"题库 {total} 题：{'✅ 全部通过安全审计' if not problems else '❌ 存在问题'}"]
        for qid, issues in problems[:5]:
            lines.append(f"  ❌ {qid}: {'；'.join(issues)}")
        lines.append("")
        for name, stat in self.agent.bank.stats().items():
            lines.append(f"{name}：{stat['题量']} 题／{stat['知识点']} 个知识点／"
                         f"难度分布 {stat['难度分布']}")
        template_issues = safety.audit_dialogue_templates(TEMPLATES)
        lines.append("")
        lines.append(f"童趣话术 {len(TEMPLATES)} 组："
                     f"{'✅ 无惩罚性/比较性表达' if not template_issues else '❌ 存在问题'}")
        lines.append("")
        lines.append(f"硬性边界：单次最多 {config.MAX_QUESTIONS_PER_ROUND} 题｜"
                     f"单元上限 {config.MAX_QUESTIONS_PER_SESSION} 题｜"
                     f"学习 {config.UNIT_MINUTES} 分钟强制休息｜"
                     f"数学上限 {config.MATH_MAX_NUMBER} 以内")
        return "\n".join(lines)

    def architecture(self) -> Dict[str, Any]:
        """工作流图与处理器绑定关系（页面可展示实时架构）。"""
        with self._lock:
            return self.agent.architecture()
