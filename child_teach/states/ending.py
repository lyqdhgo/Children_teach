# -*- coding: utf-8 -*-
"""结束学习处理器：总结今日收获、落盘记录、生成家长简报。"""
from __future__ import annotations

from .. import safety
from ..runtime.context import TurnContext
from ..runtime.conversation_graph import EV_FINISH, STATE_END
from ..runtime.intent import Intent
from ..runtime.recorder import weak_topic_labels
from ..runtime.turn import TurnResult
from .base import StateHandler, result_from_lines


class EndingHandler(StateHandler):
    """结束学习节点。"""

    node = STATE_END

    def __init__(self, welcome_handler, daily_aggregator, daily_renderer) -> None:
        self.welcome_handler = welcome_handler
        self.daily_aggregator = daily_aggregator
        self.daily_renderer = daily_renderer

    # ------------------------------------------------------------ 节点处理
    def handle(self, ctx: TurnContext, intent: Intent) -> TurnResult:
        """已结束状态下再说一句话：说「开始」就重新开始，否则温和提示。"""
        if intent.is_start:
            return self.welcome_handler.begin(ctx, reset_machine=True)
        return result_from_lines(ctx, [ctx.dialogue.say("come_back")])

    # ------------------------------------------------------------ 结束本次学习
    def finish(self, ctx: TurnContext, reason: str = "child_requested_end") -> TurnResult:
        session = ctx.session
        if session is None:
            return result_from_lines(ctx, [ctx.dialogue.say("come_back")])

        habit_progress = ctx.habits.progress()
        summary_data = {"minutes": round(ctx.minutes(), 1),
                        "habits_done": habit_progress["done"],
                        "hard_topics": weak_topic_labels(session.answers),
                        **session.summary()}
        child_text = ctx.dialogue.session_summary(summary_data)

        record = ctx.recorder.record(
            session,
            now=ctx.now(),
            reason=reason,
            questions_presented=ctx.questions_presented,
            habit_progress=habit_progress,
            state_trace=ctx.machine.trace(),
        )

        ctx.go(EV_FINISH, STATE_END)
        parent_note = self.daily_renderer.render(self.daily_aggregator.build())
        return TurnResult(
            child_text=safety.sanitize_child_text(child_text),
            state=ctx.state,
            state_path=ctx.state_path(),
            parent_note=parent_note,
            finished=True,
            meta={
                "session_id": session.session_id,
                "minutes": summary_data["minutes"],
                "tasks": session.tasks,
                "accuracy": summary_data["accuracy"],
                "stars": session.stars,
                "record": record,
            },
        )
