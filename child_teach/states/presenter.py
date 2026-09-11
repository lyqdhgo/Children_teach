# -*- coding: utf-8 -*-
"""出题器：负责「开始一组学习任务」并把题目呈现给孩子。

被「选择科目」「奖励反馈」「休息提醒」「习惯打卡」多处复用，
因此独立成服务，而不是塞进某个状态处理器里。
"""
from __future__ import annotations

from typing import List, Optional

from .. import config
from ..dialogue.engine import DialogueEngine
from ..domain.question import OPEN_KINDS
from ..domain.round import Round
from ..repository.adaptive_engine import AdaptiveEngine
from ..runtime.context import RESUME_ROUND, TurnContext
from ..runtime.conversation_graph import (EV_NEXT_ROUND, EV_PICK_SUBJECT, EV_REST_DONE,
                                          EV_TASK_READY, STATE_ANSWER, STATE_CHOOSE_SUBJECT,
                                          STATE_LEARNING, STATE_REWARD, STATE_REST)
from ..runtime.turn import TurnResult
from .base import result_from_lines
from .rest_notice import REASON_QUOTA, REASON_TIME, RestNoticeService


class RoundPresenter:
    """选题 + 状态流转 + 题目呈现。"""

    def __init__(self, dialogue: DialogueEngine, adaptive: AdaptiveEngine,
                 rest_notice: RestNoticeService) -> None:
        self.dialogue = dialogue
        self.adaptive = adaptive
        self.rest_notice = rest_notice

    # ------------------------------------------------------------ 开始一组
    def start_round(self, ctx: TurnContext, subject: str,
                    from_rest: bool = False) -> TurnResult:
        """开始一组学习任务（最多 3 题）。"""
        # 时长控制：本休息周期满 10 分钟 → 先休息，再出题
        if not from_rest and ctx.cycle_minutes() >= config.HARD_REST_MINUTES:
            return self.rest_notice.enter(ctx, REASON_TIME, resume=RESUME_ROUND,
                                          subject=subject)

        # 题量控制：一个学习单元累计不超过上限
        remaining = ctx.remaining_budget()
        if remaining <= 0:
            ctx.rest_resume = "choose"
            ctx.rest_pending_subject = None
            return self.rest_notice.enter(ctx, REASON_QUOTA, resume="choose")

        questions = self.adaptive.select(subject, min(config.MAX_QUESTIONS_PER_ROUND,
                                                      remaining), ctx.rng)
        if not questions:
            return result_from_lines(ctx, ["这个科目今天先不玩啦，我们换一个好不好呀？",
                                           self.dialogue.menu()])

        self._enter_learning(ctx)
        first_time_subject = ctx.round is None or ctx.round.subject != subject
        ctx.begin_round(Round(subject=subject, questions=list(questions)))

        ctx.go(EV_TASK_READY, STATE_ANSWER)
        prefix: List[str] = []
        if first_time_subject:
            prefix.append(self.dialogue.subject_intro(subject))
        prefix.append(self.dialogue.say("round_start", n=len(questions)))
        return self.present(ctx, prefix=prefix)

    def _enter_learning(self, ctx: TurnContext) -> None:
        """按当前节点选择合适的边进入「学习任务」。"""
        state = ctx.state
        if state == STATE_CHOOSE_SUBJECT:
            ctx.go(EV_PICK_SUBJECT, STATE_LEARNING)
        elif state == STATE_REWARD:
            ctx.go(EV_NEXT_ROUND, STATE_LEARNING)
        elif state == STATE_REST:
            ctx.go(EV_REST_DONE, STATE_LEARNING)
        elif state != STATE_LEARNING:
            ctx.go(EV_PICK_SUBJECT, STATE_LEARNING)

    # ------------------------------------------------------------ 呈现题目
    def present(self, ctx: TurnContext, prefix: Optional[List[str]] = None) -> TurnResult:
        """呈现当前题目（含可视化、拼音、选项与温和的休息预告）。"""
        round_ = ctx.round
        question = round_.current() if round_ else None
        if question is None:
            # 没有待答题：防御性回到选择科目
            if ctx.state == STATE_ANSWER:
                from ..runtime.conversation_graph import EV_SWITCH_SUBJECT
                ctx.go(EV_SWITCH_SUBJECT, STATE_CHOOSE_SUBJECT)
            return result_from_lines(ctx, [self.dialogue.menu()])

        ctx.present(question)
        lines: List[str] = list(prefix or [])
        lines.append(self.dialogue.question_text(question, round_.position, round_.total))
        if question.kind in OPEN_KINDS:
            lines.append("（慢慢说，没有标准答案哦～）")

        # 满 8 分钟温和预告一次
        if ctx.cycle_minutes() >= config.SOFT_REST_MINUTES and not ctx.soft_warned:
            lines.append(self.dialogue.say("soft_rest"))
            ctx.soft_warned = True

        return result_from_lines(ctx, lines, meta={
            "qid": question.qid,
            "subject": question.subject,
            "topic": question.topic,
            "difficulty": self.adaptive.level_for(question.subject, question.topic),
            "kind": question.kind,
            "stem": question.stem,
            "options": list(question.options),
            "index": round_.position,
            "total": round_.total,
        })
