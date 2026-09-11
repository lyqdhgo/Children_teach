# -*- coding: utf-8 -*-
"""选择科目处理器：四大模块的总入口。"""
from __future__ import annotations

from ..runtime.context import TurnContext
from ..runtime.conversation_graph import STATE_CHOOSE_SUBJECT
from ..runtime.intent import Intent
from ..runtime.turn import TurnResult
from .base import StateHandler, result_from_lines


class SubjectChoiceHandler(StateHandler):
    """选择科目：语文 / 数学 / 英语 / 习惯小游戏。"""

    node = STATE_CHOOSE_SUBJECT

    def __init__(self, presenter, habit_handler) -> None:
        self.presenter = presenter
        self.habit_handler = habit_handler

    def handle(self, ctx: TurnContext, intent: Intent) -> TurnResult:
        if intent.subject is None:
            return result_from_lines(ctx, [
                ctx.dialogue.menu(),
                ctx.dialogue.say("unknown_choice"),
            ])
        if intent.wants_habit:
            return self.habit_handler.enter(ctx)
        return self.presenter.start_round(ctx, intent.subject)
