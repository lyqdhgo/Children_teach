# -*- coding: utf-8 -*-
"""欢迎页处理器：问候 + 询问今天想学什么，也是「开始一次学习单元」的入口。"""
from __future__ import annotations

from ..dialogue.engine import DialogueEngine
from ..runtime.context import TurnContext
from ..runtime.conversation_graph import EV_GREETED, STATE_CHOOSE_SUBJECT, STATE_WELCOME
from ..runtime.intent import Intent
from ..runtime.turn import TurnResult
from .base import LaunchingHandler, result_from_lines


class WelcomeHandler(LaunchingHandler):
    """欢迎页。"""

    node = STATE_WELCOME

    def __init__(self, dialogue: DialogueEngine) -> None:
        self.dialogue = dialogue

    # ------------------------------------------------------------ 开始新单元
    def begin(self, ctx: TurnContext, reset_machine: bool = False) -> TurnResult:
        """开始（或重新开始）一次学习单元。"""
        if reset_machine or ctx.session is None:
            ctx.machine.reset(STATE_WELCOME)
        ctx.start_new_session()
        ctx.begin_turn()
        if ctx.state != STATE_WELCOME:
            ctx.force(STATE_WELCOME, "重新开始")
        ctx.go(EV_GREETED, STATE_CHOOSE_SUBJECT)
        return result_from_lines(
            ctx,
            [self.dialogue.welcome(ctx.child_name) + "\n\n" + self.dialogue.menu()],
            meta={"action": "welcome", "options": ["1", "2", "3", "4"]},
        )

    # ------------------------------------------------------------ 节点处理
    def handle(self, ctx: TurnContext, intent: Intent) -> TurnResult:
        ctx.go(EV_GREETED, STATE_CHOOSE_SUBJECT)
        return result_from_lines(ctx, [self.dialogue.menu()])
