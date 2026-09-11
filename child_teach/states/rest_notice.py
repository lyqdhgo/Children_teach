# -*- coding: utf-8 -*-
"""休息提醒服务：进入休息、重复提醒与恢复策略。

单独成类的原因：疲劳休息会被「答题」「奖励」「习惯」「情绪抵触」等多处触发，
把它抽成服务后，各处只调用 ``enter()``，不必各自复制一套时长话术。
"""
from __future__ import annotations

from typing import List, Optional

from .. import config
from ..dialogue.engine import DialogueEngine
from ..runtime.context import TurnContext
from ..runtime.conversation_graph import EV_FATIGUE, STATE_REST
from ..runtime.turn import TurnResult
from .base import result_from_lines

#: 休息时可以说的三件事（孩子只需要点一个按钮）
REST_MENU_HINT = "想继续就说「好啦」，想结束就说「结束」，想玩小游戏就说「小游戏」哦～"

#: 休息原因
REASON_TIME = "time"          # 满 10 分钟
REASON_FATIGUE = "fatigue"    # 连续答错
REASON_QUOTA = "quota"        # 单次题量达上限
REASON_REQUEST = "request"    # 孩子主动说累了


class RestNoticeService:
    """负责「该休息了」这件事的全部表达。"""

    def __init__(self, dialogue: DialogueEngine) -> None:
        self.dialogue = dialogue

    # ------------------------------------------------------------ 进入休息
    def enter(self, ctx: TurnContext, reason: str, resume: str,
              subject: Optional[str] = None, prefix: str = "") -> TurnResult:
        """进入休息提醒节点，并记下休息后要恢复到哪里。"""
        ctx.rest_resume = resume
        ctx.rest_pending_subject = subject
        if ctx.state != STATE_REST:
            ctx.go(EV_FATIGUE, STATE_REST)

        lines: List[str] = []
        if prefix:
            lines.append(prefix)
        if reason == REASON_FATIGUE:
            lines.append("我们先歇一小会儿哦，小脑袋也需要休息～")
        if reason == REASON_QUOTA:
            lines.append("今天我们玩了好多小任务啦，先歇一歇吧～")
        lines.append(self.dialogue.rest_reminder(ctx.minutes()))
        lines.append(REST_MENU_HINT)
        return result_from_lines(ctx, lines, meta={"rest_reason": reason,
                                                  "minutes": round(ctx.minutes(), 1)})

    # ------------------------------------------------------------ 重复提醒
    def reminder(self, ctx: TurnContext) -> TurnResult:
        """孩子还说「休息」时，再给一次休息建议。"""
        return result_from_lines(ctx, [self.dialogue.rest_reminder(ctx.minutes()),
                                      REST_MENU_HINT])

    def menu_hint(self, ctx: TurnContext) -> TurnResult:
        """听不懂时的兜底。"""
        return result_from_lines(ctx, [REST_MENU_HINT])

    def rest_hints(self) -> str:
        return "、".join(config.REST_HINTS)
