# -*- coding: utf-8 -*-
"""学习任务处理器：负责「这一组题」的呈现。

正常流程里本节点只做瞬时过渡（选好题就进入答题交互）；
保留处理器是为了兜底：若某次输入落在该节点上，直接呈现当前题目。
"""
from __future__ import annotations

from ..runtime.context import TurnContext
from ..runtime.conversation_graph import STATE_LEARNING
from ..runtime.intent import Intent
from ..runtime.turn import TurnResult
from .base import StateHandler


class LearningTaskHandler(StateHandler):
    """学习任务节点。"""

    node = STATE_LEARNING

    def __init__(self, presenter) -> None:
        self.presenter = presenter

    def handle(self, ctx: TurnContext, intent: Intent) -> TurnResult:
        return self.presenter.present(ctx)
