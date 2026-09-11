# -*- coding: utf-8 -*-
"""休息提醒处理器：休息后恢复到哪里，由休息前的上下文决定。"""
from __future__ import annotations

from ..dialogue.engine import DialogueEngine
from ..runtime.context import RESUME_ANSWER, RESUME_ROUND, TurnContext
from ..runtime.conversation_graph import EV_REST_DONE, STATE_ANSWER, STATE_CHOOSE_SUBJECT, STATE_REST
from ..runtime.intent import Intent
from ..runtime.turn import TurnResult
from .base import StateHandler, result_from_lines


class RestHandler(StateHandler):
    """休息提醒节点。"""

    node = STATE_REST

    def __init__(self, presenter, habit_handler, ending_handler, rest_notice,
                 dialogue: DialogueEngine) -> None:
        self.presenter = presenter
        self.habit_handler = habit_handler
        self.ending_handler = ending_handler
        self.rest_notice = rest_notice
        self.dialogue = dialogue

    # ------------------------------------------------------------ 主流程
    def handle(self, ctx: TurnContext, intent: Intent) -> TurnResult:
        ctx.soft_warned = False

        # 1) 改玩习惯小游戏
        if intent.wants_habit:
            return self.habit_handler.enter(ctx, prefix=self.dialogue.say("rest_back"))

        # 2) 直接点名要学某个科目
        if intent.subject:
            ctx.go(EV_REST_DONE, STATE_CHOOSE_SUBJECT)
            return self.presenter.start_round(ctx, intent.subject, from_rest=True)

        # 3) 休息好了 → 回到休息前的位置
        if intent.is_ack:
            return self._resume(ctx)

        # 4) 还想休息
        if intent.is_rest:
            return self.rest_notice.reminder(ctx)

        # 5) 听不懂
        return self.rest_notice.menu_hint(ctx)

    # ------------------------------------------------------------ 恢复
    def _resume(self, ctx: TurnContext) -> TurnResult:
        ctx.reset_cycle()                       # 开启新的 10 分钟周期
        round_ = ctx.round

        if ctx.rest_resume == RESUME_ANSWER and round_ is not None and not round_.is_finished():
            ctx.go(EV_REST_DONE, STATE_ANSWER)
            return self.presenter.present(ctx, prefix=[self.dialogue.say("rest_back")])

        if ctx.rest_resume == RESUME_ROUND and ctx.rest_pending_subject:
            return self.presenter.start_round(ctx, ctx.rest_pending_subject, from_rest=True)

        ctx.go(EV_REST_DONE, STATE_CHOOSE_SUBJECT)
        return result_from_lines(ctx, [self.dialogue.say("rest_back"), ctx.dialogue.menu()])
