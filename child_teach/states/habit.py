# -*- coding: utf-8 -*-
"""习惯打卡处理器（四大模块中的核心）。

流程：定今天的小目标 → 逐项引导（一次只问一件事）→ 只说做得好的地方 → 回到选科目。
「还没做到」永远不判错，只换成温和引导，并记入打卡日志为未完成。
"""
from __future__ import annotations

from typing import List

from ..runtime.context import (HABIT_STAGE_GOAL, HABIT_STAGE_ITEMS, TurnContext)
from ..runtime.conversation_graph import (EV_FATIGUE, EV_HABIT_DONE, EV_PICK_HABIT,
                                          EV_REST_DONE, STATE_CHOOSE_SUBJECT, STATE_HABIT,
                                          STATE_REWARD, STATE_REST)
from ..runtime.intent import Intent
from ..runtime.turn import TurnResult
from .base import StateHandler, result_from_lines


class HabitHandler(StateHandler):
    """习惯打卡节点。"""

    node = STATE_HABIT

    def __init__(self, presenter) -> None:
        self.presenter = presenter

    # ------------------------------------------------------------ 进入模块
    def enter(self, ctx: TurnContext, prefix: str = "") -> TurnResult:
        state = ctx.state
        if state == STATE_CHOOSE_SUBJECT:
            ctx.go(EV_PICK_HABIT, STATE_HABIT)
        elif state == STATE_REWARD:
            ctx.go(EV_PICK_HABIT, STATE_HABIT)
        elif state == STATE_REST:
            ctx.go(EV_REST_DONE, STATE_HABIT)
        elif state != STATE_HABIT:
            ctx.go(EV_FATIGUE, STATE_REST)
            ctx.go(EV_REST_DONE, STATE_HABIT)

        ctx.habit_asked = set()
        existing_goal = ctx.habits.goal()
        ctx.habit_stage = HABIT_STAGE_ITEMS if existing_goal else HABIT_STAGE_GOAL

        lines: List[str] = [prefix] if prefix else []
        lines.append(ctx.dialogue.say("habit_intro"))
        if ctx.habit_stage == HABIT_STAGE_GOAL:
            lines.append(ctx.dialogue.say("habit_goal_hint"))
        else:
            lines.append(f"今天的小目标还是「{existing_goal}」，我们继续加油～")
            item = ctx.next_habit_item()
            if item is None:
                return self._finish(ctx, lines)
            lines.append(ctx.dialogue.say("habit_ask", prompt=item.child_prompt))
        return result_from_lines(ctx, lines, meta={"habit_stage": ctx.habit_stage})

    # ------------------------------------------------------------ 节点处理
    def handle(self, ctx: TurnContext, intent: Intent) -> TurnResult:
        # 打卡期间也可以直接切到学习科目
        if intent.subject and not intent.wants_habit:
            ctx.go(EV_HABIT_DONE, STATE_CHOOSE_SUBJECT)
            return self.presenter.start_round(ctx, intent.subject)

        # 第一步：定今天的小目标
        if ctx.habit_stage == HABIT_STAGE_GOAL:
            goal = intent.raw or "今天开心学习"
            ctx.habits.set_goal(goal)
            ctx.habit_stage = HABIT_STAGE_ITEMS
            lines = [ctx.dialogue.say("habit_goal_saved", goal=goal)]
            item = ctx.next_habit_item()
            if item is None:
                return self._finish(ctx, lines)
            lines.append(ctx.dialogue.say("habit_ask", prompt=item.child_prompt))
            return result_from_lines(ctx, lines, meta={"habit_goal": goal})

        # 第二步：逐项打卡
        item = ctx.next_habit_item()
        if item is None:
            return self._finish(ctx, [])

        done = not ctx.classifier.is_negative(intent.raw)
        ctx.habits.check(item.key, done)
        ctx.habit_asked.add(item.key)
        if ctx.session is not None:
            ctx.session.tasks += 1

        lines = [ctx.dialogue.say("check_done" if done else "check_later",
                                  cheer=item.cheer_done if done else item.cheer_later)]
        star_text = ctx.grant_star()
        if star_text:
            lines.append(star_text)

        next_item = ctx.next_habit_item()
        if next_item is None:
            return self._finish(ctx, lines)
        lines.append(ctx.dialogue.say("habit_ask", prompt=next_item.child_prompt))
        return result_from_lines(ctx, lines, meta={"habit_item": item.key,
                                                   "habit_done": done})

    # ------------------------------------------------------------ 结束打卡
    def _finish(self, ctx: TurnContext, lines: List[str]) -> TurnResult:
        ctx.go(EV_HABIT_DONE, STATE_CHOOSE_SUBJECT)
        lines.append(ctx.dialogue.say("habit_finish",
                                      progress=ctx.habits.child_progress_text()))
        lines.append(ctx.dialogue.menu())
        return result_from_lines(ctx, lines, meta={"habit_progress": ctx.habits.progress()})
