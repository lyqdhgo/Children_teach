# -*- coding: utf-8 -*-
"""奖励反馈处理器：一组做完后的「再玩一组 / 换科目 / 今天到这里」。"""
from __future__ import annotations

from .. import config
from ..runtime.context import TurnContext
from ..runtime.conversation_graph import EV_SWITCH_SUBJECT, STATE_CHOOSE_SUBJECT, STATE_REWARD
from ..runtime.intent import Intent
from ..runtime.turn import TurnResult
from .base import StateHandler, result_from_lines


class RewardHandler(StateHandler):
    """奖励反馈节点。"""

    node = STATE_REWARD

    def __init__(self, presenter, habit_handler, ending_handler) -> None:
        self.presenter = presenter
        self.habit_handler = habit_handler
        self.ending_handler = ending_handler

    def handle(self, ctx: TurnContext, intent: Intent) -> TurnResult:
        raw = intent.raw

        if intent.is_switch or raw == "2":                     # 换个科目
            ctx.go(EV_SWITCH_SUBJECT, STATE_CHOOSE_SUBJECT)
            return result_from_lines(ctx, [ctx.dialogue.menu()])

        if raw == "3":                                          # 今天到这里
            return self.ending_handler.finish(ctx, "child_requested_end")

        if intent.wants_habit:                                  # 习惯小游戏
            return self.habit_handler.enter(ctx)

        if raw == "1" or intent.is_continue or intent.is_ack:   # 再玩一组
            subject = ctx.round.subject if ctx.round else config.SUBJECT_CHINESE
            return self.presenter.start_round(ctx, subject)

        return result_from_lines(ctx, [ctx.dialogue.say("after_round_menu")])
