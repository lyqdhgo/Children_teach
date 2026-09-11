# -*- coding: utf-8 -*-
"""守卫链：每轮输入先过这些横切检查，再交给节点处理器。

顺序即优先级（责任链）：
    1. SensitiveGuard  敏感内容 —— 最高优先级，不展开讨论，记录并转交家长
    2. HelpGuard       「我不会」—— 是求助不是抵触，给启发式提示
    3. ResistanceGuard 情绪抵触 —— 不强迫做题，切小游戏 / 休息 / 结束
    4. EndRequestGuard 「结束」  —— 任何节点都可以结束学习

放在守卫里而不是散落在各状态里的原因：这些规则与「当前在哪个状态」无关，
属于横切关注点；集中在一处才好审计「禁止强迫做题」「禁止惩罚」这类约束。
"""
from __future__ import annotations

from typing import List, Optional

from .. import config
from ..infra import now_iso
from ..runtime.context import RESUME_ANSWER, RESUME_CHOOSE, TurnContext
from ..runtime.conversation_graph import EV_FATIGUE, STATE_ANSWER, STATE_REST
from ..runtime.intent import Intent
from ..runtime.turn import TurnResult
from .base import TurnGuard, result_from_lines
from .rest_notice import REST_MENU_HINT


class SensitiveGuard(TurnGuard):
    """敏感内容：不展开、不评判，记录时间与原文，并在家长简报里提示。"""

    name = "敏感内容守卫"
    order = 20

    def intercept(self, ctx: TurnContext, intent: Intent) -> Optional[TurnResult]:
        if not intent.is_sensitive:
            return None
        record = {"type": "sensitive", "text": intent.raw[:80], "at": now_iso()}
        if ctx.session is not None:
            ctx.session.add_watch_item(record)
        ctx.profile.add_watch_item(record)

        ctx.rest_resume = RESUME_CHOOSE
        ctx.rest_pending_subject = None
        if ctx.state != STATE_REST:
            ctx.go(EV_FATIGUE, STATE_REST)
        return result_from_lines(
            ctx,
            [ctx.dialogue.say("sensitive"), REST_MENU_HINT],
            note="需关注：孩子提到敏感内容，已记录时间与原文，请在合适时机温和沟通。",
            meta={"sensitive": True},
        )


class HelpGuard(TurnGuard):
    """「我不会」是求助：给启发式提示，而不是判错、更不是换话题。"""

    name = "求助守卫"
    order = 30

    def intercept(self, ctx: TurnContext, intent: Intent) -> Optional[TurnResult]:
        if not intent.is_help:
            return None
        question = ctx.current_question
        if ctx.state == STATE_ANSWER and question is not None:
            lines = [ctx.dialogue.hint(question)]
            if not ctx.retry_used:
                ctx.retry_used = True          # 提示过但仍留在同一题
            else:
                lines.append(ctx.dialogue.reveal_answer(question))
            return result_from_lines(ctx, lines, meta={"help": True})
        return result_from_lines(ctx, ["好呀，那我们换个轻松的～", ctx.dialogue.menu()],
                                 meta={"help": True})


class ResistanceGuard(TurnGuard):
    """情绪抵触：立刻停止出题，允许小游戏 / 休息 / 结束三选一（不强迫）。"""

    name = "抵触情绪守卫"
    order = 40

    def intercept(self, ctx: TurnContext, intent: Intent) -> Optional[TurnResult]:
        if not intent.is_resistance or intent.is_end:
            return None
        if ctx.session is not None:
            ctx.session.add_watch_item({
                "type": "resistance", "text": intent.raw[:60],
                "at": now_iso(), "state": ctx.state,
            })
        ctx.rest_resume = RESUME_CHOOSE
        ctx.rest_pending_subject = None
        if ctx.state != STATE_REST:
            ctx.go(EV_FATIGUE, STATE_REST)
        return result_from_lines(ctx, [
            ctx.dialogue.say("resistance"),
            "（说「小游戏」我们玩习惯小游戏，说「休息」就歇一会儿，说「结束」就今天到这里～）",
        ], meta={"resistance": True})


class EndRequestGuard(TurnGuard):
    """明确的结束指令：任何节点都可以结束本次学习。"""

    name = "结束守卫"
    order = 50

    def __init__(self, ending_handler) -> None:
        self.ending_handler = ending_handler

    def intercept(self, ctx: TurnContext, intent: Intent) -> Optional[TurnResult]:
        if not intent.is_end:
            return None
        return self.ending_handler.finish(ctx, "child_requested_end")


def default_guards(ending_handler, rest_notice=None) -> List[TurnGuard]:
    """按优先级返回默认守卫链。"""
    guards = [SensitiveGuard(), HelpGuard(), ResistanceGuard(),
              EndRequestGuard(ending_handler)]
    return sorted(guards, key=lambda guard: guard.order)
