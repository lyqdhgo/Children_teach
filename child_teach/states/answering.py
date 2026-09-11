# -*- coding: utf-8 -*-
"""答题交互处理器：本项目的核心业务规则集中在这里。

规则（与需求一一对应）：
    * 答错不否定：第一次答错只给启发式提示，不记录、不计分；
    * 一题只记一次：提示后仍不会 → 温柔给答案再翻页；
    * 答对不啰嗦：给具体表扬，达 3 个小任务发星星；
    * 疲劳即休息：连续答错达上限 → 强制进入休息提醒；
    * 一组 3 题：做完进入奖励反馈，绝不一口气刷题。
"""
from __future__ import annotations

from typing import List

from .. import config
from ..infra import now_iso
from ..runtime.context import RESUME_ANSWER, TurnContext
from ..runtime.conversation_graph import (EV_ANSWER_SUBMIT, EV_ROUND_DONE, STATE_ANSWER,
                                          STATE_REWARD)
from ..runtime.intent import Intent
from ..runtime.turn import TurnResult
from .base import StateHandler, result_from_lines


class AnsweringHandler(StateHandler):
    """答题交互节点。"""

    node = STATE_ANSWER

    def __init__(self, presenter, rest_notice) -> None:
        self.presenter = presenter
        self.rest_notice = rest_notice

    # ------------------------------------------------------------ 主流程
    def handle(self, ctx: TurnContext, intent: Intent) -> TurnResult:
        question = ctx.current_question
        if question is None:
            return self.presenter.present(ctx)
        if intent.is_empty:
            return result_from_lines(ctx, [ctx.dialogue.say("unknown")])

        correct, graded = question.matches(intent.raw)

        # ---- 第一次答错：只启发，不记录、不计分（避免一题算两次）----
        if graded and not correct and not ctx.retry_used:
            ctx.retry_used = True
            return result_from_lines(ctx, [ctx.dialogue.hint(question)],
                                     meta={"graded": True, "correct": False, "retry": True})

        # ---- 到这里才是这道题的最终结果：一题只记一次 ----
        info = ctx.adaptive.record_answer(question, correct, graded)
        # assisted = 提示之后自己做了出来（只统计真的答对的：家长报告既不虚高也不虚低）
        assisted = bool(ctx.retry_used and correct)
        self._record(ctx, question, intent.raw, correct, graded, assisted)

        lines = self._feedback_lines(ctx, question, correct, graded, assisted, info)

        # ---- 前进到下一题 / 奖励 / 休息 ----
        ctx.clear_question()
        if ctx.round is not None:
            ctx.round.advance()

        star_text = ctx.grant_star()
        if star_text:
            lines.append(star_text)

        if ctx.consecutive_wrong >= config.FATIGUE_WRONG_LIMIT:
            return self.rest_notice.enter(ctx, "fatigue", resume=RESUME_ANSWER,
                                          prefix="\n".join(lines))

        if ctx.round is not None and ctx.round.is_finished():
            ctx.go(EV_ROUND_DONE, STATE_REWARD)
            lines.append(ctx.dialogue.say("round_done"))
            lines.append(ctx.dialogue.say("after_round_menu"))
            return result_from_lines(ctx, lines, meta={"round_done": True,
                                                       "stars": ctx.session.stars})

        ctx.go(EV_ANSWER_SUBMIT, STATE_ANSWER)
        return self.presenter.present(ctx, prefix=lines)

    # ------------------------------------------------------------ 记录与话术
    @staticmethod
    def _record(ctx: TurnContext, question, raw: str, correct: bool, graded: bool,
                assisted: bool) -> None:
        """写入一条作答记录（同时更新难度与统计）。"""
        ctx.session.add_answer({
            "qid": question.qid,
            "subject": question.subject,
            "topic": question.topic,
            "difficulty": question.difficulty,
            "kind": question.kind,
            "input": raw[:40],
            "correct": bool(correct),
            "graded": bool(graded),
            "assisted": assisted,
            "at": now_iso(),
        }, graded, correct)
        if graded:
            ctx.consecutive_wrong = 0 if correct else ctx.consecutive_wrong + 1

    def _feedback_lines(self, ctx: TurnContext, question, correct: bool, graded: bool,
                        assisted: bool, info: dict) -> List[str]:
        if graded and not correct:
            # 提示后仍然不会：温柔给出答案，然后翻页（不惩罚、不重复刷题）
            lines = [ctx.dialogue.hint(question), ctx.dialogue.reveal_answer(question)]
        else:
            level = ctx.adaptive.level_for(question.subject, question.topic)
            lines = [ctx.dialogue.feedback(question, correct, graded, level)]
            if assisted and graded:
                lines.append("你想出来啦，真棒！🌟")
        if info.get("just_mastered"):
            lines.append("这个本领你已经学会啦，好厉害！🌟")
        return lines
