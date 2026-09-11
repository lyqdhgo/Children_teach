# -*- coding: utf-8 -*-
"""7 岁儿童启蒙教辅 Agent —— 包入口。

分层结构（详见 docs/architecture.md）：
    domain      领域对象（题目 / 学习轮次 / 学习单元 / 习惯项）
    infra       基础设施（时钟、本地 JSON 仓储）
    safety      安全边界（超纲审计 / 话术红线 / 情绪识别）
    repository  仓储与引擎（题库 / 自适应难度 / 习惯打卡）
    dialogue    童趣话术与系统提示词
    report      家长报告（聚合 / 渲染 / 问答）
    runtime     运行机制（意图 / 工作流图 / 状态机 / 上下文 / 奖励 / 记录）
    states      工作流节点处理器与守卫链
    webui       本地网页界面

四大模块：语文启蒙 / 数学启蒙 / 英语启蒙 / 学习习惯养成。
两套对话接口：面向孩子（童趣）/ 面向家长（简洁客观）。
"""
from __future__ import annotations

from .agent import ChildTutorAgent
from .dialogue.engine import DialogueEngine
from .dialogue.templates import TEMPLATES
from .domain.habit import DAY_GOAL_ITEMS, HABIT_ITEMS, ITEMS_BY_KEY, HabitItem
from .domain.question import Question
from .domain.round import Round
from .domain.session import Session
from .infra.clock import Clock, FrozenClock, SystemClock, as_clock
from .infra import ChildDataStore, DataHub, JsonStore
from .report.qa import ParentQAService
from .repository.adaptive_engine import AdaptiveEngine
from .repository.habit_repository import HabitRepository
from .repository.question_repository import QuestionRepository, build_default_repository
from .runtime.conversation_graph import STATE_ORDER, build_conversation_workflow
from .runtime.intent import Intent, IntentClassifier
from .runtime.state_machine import InvalidTransition, StateMachine
from .runtime.turn import TurnResult
from .runtime.workflow import WorkflowGraph

__all__ = [
    # 主入口
    "ChildTutorAgent", "TurnResult",
    # 领域
    "Question", "Round", "Session", "HabitItem", "HABIT_ITEMS", "ITEMS_BY_KEY",
    "DAY_GOAL_ITEMS",
    # 基础设施
    "Clock", "SystemClock", "FrozenClock", "as_clock", "JsonStore", "ChildDataStore",
    "DataHub",
    # 仓储与引擎
    "QuestionRepository", "build_default_repository", "AdaptiveEngine", "HabitRepository",
    # 对话
    "DialogueEngine", "TEMPLATES",
    # 报告
    "ParentQAService",
    # 运行机制
    "Intent", "IntentClassifier", "StateMachine", "InvalidTransition",
    "WorkflowGraph", "build_conversation_workflow", "STATE_ORDER",
]

__version__ = "2.0.0"
