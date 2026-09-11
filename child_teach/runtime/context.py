# -*- coding: utf-8 -*-
"""运行上下文：一次学习单元里所有处理器共享的状态（Context 对象）。

状态处理器（``states``）不再各自攥着一堆字段，而是统一读写 Context：
    * 协作对象（仓储 / 引擎 / 状态机 / 奖励 / 记录器）由外观层注入，只读；
    * 会话态（本次星星、当前题目、休息周期、打卡进度）由处理器就地更新。
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from .. import config
from ..dialogue.engine import DialogueEngine
from ..domain.habit import HabitItem
from ..domain.question import Question
from ..domain.round import Round
from ..domain.session import Session

from ..infra import ChildDataStore, Clock
from ..repository.adaptive_engine import AdaptiveEngine
from ..repository.habit_repository import HabitRepository
from ..repository.question_repository import QuestionRepository
from .intent import IntentClassifier
from .recorder import SessionRecorder
from .rewards import RewardService
from .state_machine import InvalidTransition, StateMachine

#: 休息后要恢复到的位置
RESUME_ANSWER = "answer"          # 继续本组剩下的题
RESUME_ROUND = "start_round"      # 开始新的一组
RESUME_CHOOSE = "choose"          # 回到选择科目

#: 习惯打卡流程的两个阶段
HABIT_STAGE_GOAL = "goal"
HABIT_STAGE_ITEMS = "items"


class TurnContext:
    """一次学习单元的全部运行态。"""

    def __init__(self, *, child_name: str, clock: Clock, data_store: ChildDataStore,
                 repository: QuestionRepository, adaptive: AdaptiveEngine,
                 habits: HabitRepository, dialogue: DialogueEngine,
                 machine: StateMachine, rewards: RewardService,
                 recorder: SessionRecorder,
                 classifier: Optional[IntentClassifier] = None,
                 rng: Optional[random.Random] = None) -> None:
        # ---------------- 协作对象（只读依赖） ----------------
        self.child_name = child_name
        self.clock = clock
        self.data_store = data_store
        self.repository = repository
        self.adaptive = adaptive
        self.habits = habits
        self.dialogue = dialogue
        self.machine = machine
        self.rewards = rewards
        self.recorder = recorder
        self.classifier = classifier or IntentClassifier()
        self.rng = rng or random.Random()

        # ---------------- 会话态 ----------------
        self.session: Optional[Session] = None
        self.round: Optional[Round] = None
        self.current_question: Optional[Question] = None
        self.retry_used = False
        self.consecutive_wrong = 0
        self.questions_presented = 0
        self.cycle_started_at: datetime = self.clock.now()
        self.soft_warned = False
        self.rest_resume = RESUME_CHOOSE
        self.rest_pending_subject: Optional[str] = None
        self.habit_asked: Set[str] = set()
        self.habit_stage = HABIT_STAGE_GOAL
        self.turn_path: List[str] = [self.machine.state]

    # =================================================================== #
    # 时间
    # =================================================================== #
    def now(self) -> datetime:
        return self.clock.now()

    def minutes(self) -> float:
        """本次学习累计分钟数。"""
        return self.session.minutes(self.now()) if self.session else 0.0

    def cycle_minutes(self) -> float:
        """当前休息周期内的分钟数（满 10 分钟强制休息）。"""
        return max(0.0, (self.now() - self.cycle_started_at).total_seconds() / 60.0)

    def reset_cycle(self) -> None:
        """休息结束后开启新的 10 分钟周期。"""
        self.cycle_started_at = self.now()
        self.soft_warned = False

    # =================================================================== #
    # 会话生命周期
    # =================================================================== #
    def start_new_session(self) -> Session:
        """开始一次新的学习单元（重新开始也走这里）。"""
        self.session = Session(session_id=uuid.uuid4().hex[:12], started_at=self.now())
        self.round = None
        self.current_question = None
        self.retry_used = False
        self.consecutive_wrong = 0
        self.questions_presented = 0
        self.soft_warned = False
        self.rest_resume = RESUME_CHOOSE
        self.rest_pending_subject = None
        self.habit_asked = set()
        self.habit_stage = HABIT_STAGE_GOAL
        self.cycle_started_at = self.now()
        return self.session

    # =================================================================== #
    # 状态流转
    # =================================================================== #
    def begin_turn(self) -> None:
        """开始一轮对话时记录轨迹起点。"""
        self.turn_path = [self.machine.state]

    def go(self, event: str, target: Optional[str] = None) -> str:
        """按图流转（优先走校验，安全分支允许强制跳转）。"""
        try:
            state = self.machine.fire(event, target)
        except InvalidTransition:
            if target is None:
                raise
            state = self.machine.force(target, event)
        self.turn_path.append(state)
        return state

    def force(self, target: str, event: str) -> str:
        state = self.machine.force(target, event)
        self.turn_path.append(state)
        return state

    @property
    def state(self) -> str:
        return self.machine.state

    def state_path(self) -> List[str]:
        """本轮去重后的节点轨迹。"""
        out: List[str] = []
        for node in self.turn_path:
            if not out or out[-1] != node:
                out.append(node)
        return out

    # =================================================================== #
    # 题目
    # =================================================================== #
    def begin_round(self, round_: Round) -> None:
        self.round = round_
        self.current_question = None
        self.retry_used = False
        if self.session is not None:
            self.session.rounds += 1
            self.session.start_subject(round_.subject)

    def present(self, question: Question) -> None:
        """呈现一道题：计入题量、重置提示位。"""
        self.current_question = question
        self.retry_used = False
        self.questions_presented += 1

    def clear_question(self) -> None:
        self.current_question = None
        self.retry_used = False

    def remaining_budget(self) -> int:
        """本单元还剩多少题量的额度。"""
        return max(0, config.MAX_QUESTIONS_PER_SESSION - self.questions_presented)

    @property
    def round_position(self) -> int:
        return self.round.position if self.round else 0

    @property
    def round_total(self) -> int:
        return self.round.total if self.round else 0

    # =================================================================== #
    # 星星与打卡
    # =================================================================== #
    def grant_star(self) -> str:
        """达到 3 个小任务就给一颗星，返回童趣文案（空 = 本次不发）。"""
        return self.rewards.grant_if_due(self.session, self.dialogue)

    def next_habit_item(self) -> Optional[HabitItem]:
        return self.habits.next_pending_item(exclude=self.habit_asked)

    @property
    def profile(self):
        return self.data_store.profile

    @property
    def stars(self) -> int:
        return self.data_store.profile.stars

    # =================================================================== #
    # 对外状态快照（Web / CLI 共用）
    # =================================================================== #
    def status(self) -> Dict[str, Any]:
        session = self.session
        return {
            "state": self.machine.state,
            "trace": self.machine.trace(),
            "subject": self.round.subject if self.round else None,
            "session_minutes": round(self.minutes(), 1),
            "cycle_minutes": round(self.cycle_minutes(), 1),
            "questions_presented": self.questions_presented,
            "round": f"{self.round_position}/{self.round_total}",
            "consecutive_wrong": self.consecutive_wrong,
            "tasks": session.tasks if session else 0,
            "graded": session.graded if session else 0,
            "accuracy": round(session.accuracy, 2) if session else 0.0,
            "stars": self.stars,
            "habit_stage": self.habit_stage,
        }
