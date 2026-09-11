# -*- coding: utf-8 -*-
"""主 Agent：外观（Facade）+ 组合根（Composition Root）。

这个类只做三件事：
    1. 在构造时把仓储、引擎、工作流路由装配起来（依赖注入，方便替换与测试）；
    2. 对外只暴露两个对话接口：``handle()``（面向孩子）/ ``parent_ask()``（面向家长）；
    3. 启动时自检工作流图与处理器的绑定关系，避免「图改了、代码忘了改」。

业务规则不在这里——它们分别在：
    ``states``     每个状态一个处理器（状态模式）+ 守卫链（责任链）
    ``repository`` 题库、自适应难度、习惯打卡
    ``report``     家长侧数据聚合与渲染
    ``safety``     超纲 / 话术 / 情绪三类安全边界
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Dict, Optional

from . import config
from .dialogue.engine import DialogueEngine
from .infra.clock import Clock, as_clock
from .infra import ChildDataStore
from .report.aggregator import DailySummaryAggregator, WeeklySummaryAggregator
from .report.qa import ParentQAService
from .report.renderers import DailyReportRenderer, WeeklyReportRenderer
from .repository.adaptive_engine import AdaptiveEngine
from .repository.habit_repository import HabitRepository
from .repository.question_repository import QuestionRepository, build_default_repository
from .runtime.context import TurnContext
from .runtime.conversation_graph import CONVERSATION_WORKFLOW
from .runtime.intent import IntentClassifier
from .runtime.recorder import SessionRecorder
from .runtime.rewards import RewardService, StarRewardPolicy
from .runtime.state_machine import StateMachine
from .runtime.turn import TurnResult
from .runtime.workflow import WorkflowGraph
from .states.router import ConversationRouter, build_router


class ChildTutorAgent:
    """7 岁儿童启蒙教辅 Agent（后端逻辑，无前端页面）。"""

    def __init__(self, data_dir: Optional[Path] = None, child_name: str = "小朋友",
                 repository: Optional[QuestionRepository] = None,
                 clock: Optional[object] = None,
                 rng: Optional[random.Random] = None,
                 graph: Optional[WorkflowGraph] = None) -> None:
        self.rng = rng or random.Random()
        self.clock: Clock = as_clock(clock)

        # ---------------- 数据（本地 JSON） ----------------
        self.data_store = ChildDataStore(Path(data_dir) if data_dir else config.DATA_DIR)
        if child_name and child_name != "小朋友":
            self.data_store.profile.set_child_name(child_name)
        self.child_name = self.data_store.profile.child_name

        # ---------------- 领域仓储与引擎 ----------------
        self.repository: QuestionRepository = repository or build_default_repository()
        self.adaptive = AdaptiveEngine(self.data_store.profile, self.repository)
        self.habits = HabitRepository(self.data_store.habits)
        self.dialogue = DialogueEngine(self.rng)

        # ---------------- 运行机制（图 / 状态机 / 奖励 / 记录） ----------------
        self.graph: WorkflowGraph = graph or CONVERSATION_WORKFLOW
        self.machine = StateMachine(self.graph)
        self.rewards = RewardService(StarRewardPolicy(), self.data_store.profile)
        self.recorder = SessionRecorder(self.data_store, self.adaptive)
        self.router: ConversationRouter = build_router(
            self.dialogue, self.adaptive, self.habits, self.data_store, self.graph
        )

        # ---------------- 家长侧报告 ----------------
        self.daily_aggregator = DailySummaryAggregator(self.data_store, self.habits)
        self.weekly_aggregator = WeeklySummaryAggregator(self.data_store, self.habits)
        self.daily_renderer = DailyReportRenderer()
        self.weekly_renderer = WeeklyReportRenderer()
        self.parent_qa = ParentQAService(self.data_store, self.habits)

        # ---------------- 运行上下文 ----------------
        self.ctx = TurnContext(
            child_name=self.child_name,
            clock=self.clock,
            data_store=self.data_store,
            repository=self.repository,
            adaptive=self.adaptive,
            habits=self.habits,
            dialogue=self.dialogue,
            machine=self.machine,
            rewards=self.rewards,
            recorder=self.recorder,
            classifier=IntentClassifier(),
            rng=self.rng,
        )
        self._self_check()

    # =================================================================== #
    # 启动自检
    # =================================================================== #
    def _self_check(self) -> None:
        """启动即校验：工作流图健康 + 每个节点都绑定了处理器。"""
        problems = self.graph.validate()
        if problems:
            raise RuntimeError("工作流图存在结构问题：\n- " + "\n- ".join(problems))
        bound = set(self.router.registry.states())
        missing = [name for name in self.graph.nodes if name not in bound]
        if missing:
            raise RuntimeError(f"以下节点没有绑定处理器：{missing}")

    # =================================================================== #
    # 孩子侧接口
    # =================================================================== #
    def start(self) -> TurnResult:
        """进入欢迎页：问候 + 询问今天想学什么。"""
        return self.router.launch(self.ctx)

    def handle(self, text: str) -> TurnResult:
        """孩子在任意时刻说的一句话 → 一轮童趣回复。"""
        return self.router.route(self.ctx, text)

    # =================================================================== #
    # 家长侧接口
    # =================================================================== #
    def parent_summary(self, day: Optional[str] = None) -> str:
        """今日家长简报（简洁客观）。"""
        return self.daily_renderer.render(self.daily_aggregator.build(day))

    def parent_weekly(self, day: Optional[str] = None) -> str:
        """最近 7 天习惯与学习周报。"""
        return self.weekly_renderer.render(self.weekly_aggregator.build(day))

    def parent_ask(self, query: str, day: Optional[str] = None) -> str:
        """家长追问，只答事实、不超过 3 句。"""
        return self.parent_qa.answer(query, day)

    # =================================================================== #
    # 状态快照与架构自描述
    # =================================================================== #
    def status(self) -> Dict[str, Any]:
        """当前运行状态快照（CLI / Web 共用）。"""
        snapshot = self.ctx.status()
        snapshot["trace"] = self.machine.trace()
        return snapshot

    def architecture(self) -> Dict[str, Any]:
        """返回工作流结构（节点 / 边 / Mermaid 图），用于文档与 ``--graph``。"""
        return {
            "graph": self.graph.to_dict(),
            "mermaid": self.graph.to_mermaid(),
            "handlers": self.router.registry.describe(),
            "guards": [{"name": guard.name, "order": guard.order}
                       for guard in self.router.guards],
            "validate": self.graph.validate(),
        }

    # =================================================================== #
    # 兼容旧属性名（保持 CLI / Web / 测试代码简洁）
    # =================================================================== #
    @property
    def hub(self) -> ChildDataStore:
        return self.data_store

    @property
    def bank(self) -> QuestionRepository:
        return self.repository

    @property
    def session(self):
        return self.ctx.session

    @property
    def current_question(self):
        return self.ctx.current_question

    @property
    def questions_presented(self) -> int:
        return self.ctx.questions_presented

    @property
    def habit_stage(self) -> str:
        return self.ctx.habit_stage

    def __repr__(self) -> str:  # pragma: no cover
        return (f"<ChildTutorAgent 孩子={self.child_name} 状态={self.machine.state} "
                f"星星={self.data_store.profile.stars}>")
