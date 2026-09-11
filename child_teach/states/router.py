# -*- coding: utf-8 -*-
"""工作流路由器：意图识别 → 守卫链 → 节点处理器 → 结果回填。

它是「图」与「代码」的汇合点：
    * ``HandlerRegistry`` 按工作流图的节点绑定处理器，启动时就校验有没有漏绑定，
      避免出现「图里加了状态、代码忘了实现」这种漂移；
    * 守卫链处理与状态无关的横切规则（安全 / 求助 / 抵触 / 结束）。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..report.aggregator import DailySummaryAggregator
from ..report.renderers import DailyReportRenderer
from ..runtime.context import TurnContext
from ..runtime.conversation_graph import CONVERSATION_WORKFLOW, STATE_END
from ..runtime.intent import Intent
from ..runtime.turn import TurnResult
from ..runtime.workflow import WorkflowGraph
from .answering import AnsweringHandler
from .base import LaunchingHandler, StateHandler, TurnGuard
from .ending import EndingHandler
from .guards import default_guards
from .habit import HabitHandler
from .learning import LearningTaskHandler
from .presenter import RoundPresenter
from .rest import RestHandler
from .rest_notice import RestNoticeService
from .reward import RewardHandler
from .subject_choice import SubjectChoiceHandler
from .welcome import WelcomeHandler


# --------------------------------------------------------------------------- #
# 处理器注册表
# --------------------------------------------------------------------------- #
class HandlerRegistry:
    """节点名 → 处理器实例。"""

    def __init__(self, handlers: Dict[str, StateHandler]) -> None:
        self._handlers = dict(handlers)

    @classmethod
    def from_graph(cls, graph: WorkflowGraph,
                   handlers_by_class: Dict[str, StateHandler]) -> "HandlerRegistry":
        """按图的 ``node.handler`` 字段绑定处理器，缺失即报错（防代码与图漂移）。"""
        mapping: Dict[str, StateHandler] = {}
        missing: List[str] = []
        for name, node in graph.nodes.items():
            handler = handlers_by_class.get(node.handler)
            if handler is None:
                missing.append(f"{name} → {node.handler or '未指定处理器'}")
            else:
                mapping[name] = handler
        if missing:
            raise ValueError("工作流节点缺少处理器：" + "；".join(missing))
        return cls(mapping)

    def for_state(self, state: str) -> StateHandler:
        try:
            return self._handlers[state]
        except KeyError as exc:                       # pragma: no cover - 防御
            raise KeyError(f"节点没有绑定处理器：{state}") from exc

    def states(self) -> List[str]:
        return list(self._handlers)

    def describe(self) -> Dict[str, str]:
        return {state: handler.handler_name() for state, handler in self._handlers.items()}


# --------------------------------------------------------------------------- #
# 路由器
# --------------------------------------------------------------------------- #
class ConversationRouter:
    """把一轮孩子输入路由到正确的处理器。"""

    def __init__(self, registry: HandlerRegistry, guards: List[TurnGuard]) -> None:
        self.registry = registry
        self.guards = sorted(guards, key=lambda guard: guard.order)

    # ------------------------------------------------------------ 路由
    def launch(self, ctx: TurnContext) -> TurnResult:
        """启动一次学习单元（由入口节点的处理器负责）。"""
        ctx.begin_turn()
        handler = self.registry.for_state(ctx.machine.graph.entry)
        if not isinstance(handler, LaunchingHandler):
            raise TypeError(f"入口节点处理器必须实现 LaunchingHandler：{handler}")
        intent = ctx.classifier.classify("开始")
        return self._finalize(ctx, handler.begin(ctx, reset_machine=True), intent)

    def route(self, ctx: TurnContext, text: str) -> TurnResult:
        ctx.begin_turn()
        intent = ctx.classifier.classify(text)

        # 「结束学习」节点只做收尾（重新开始 / 温和提示）：
        # 此时不再跑守卫，避免把已结束的对话又拉回休息或再次落盘记录。
        if ctx.state != STATE_END:
            for guard in self.guards:
                intercepted = guard.intercept(ctx, intent)
                if intercepted is not None:
                    return self._finalize(ctx, intercepted, intent)

        handler = self.registry.for_state(ctx.state)
        result = handler.handle(ctx, intent)
        return self._finalize(ctx, result, intent)

    # ------------------------------------------------------------ 收尾
    @staticmethod
    def _finalize(ctx: TurnContext, result: TurnResult, intent: Intent) -> TurnResult:
        result.with_state(ctx.state, ctx.state_path())
        result.meta.setdefault("intent", intent.kind)
        return result

    def describe(self) -> Dict[str, object]:
        return {
            "guards": [{"name": g.name, "order": g.order} for g in self.guards],
            "handlers": self.registry.describe(),
        }


# --------------------------------------------------------------------------- #
# 组装（组合根的一部分）
# --------------------------------------------------------------------------- #
def build_router(dialogue, adaptive, habits, data_store,
                 graph: Optional[WorkflowGraph] = None) -> ConversationRouter:
    """把服务与处理器装配成路由器（依赖注入，全部由外部提供）。"""
    graph = graph or CONVERSATION_WORKFLOW

    rest_notice = RestNoticeService(dialogue)
    presenter = RoundPresenter(dialogue, adaptive, rest_notice)

    welcome = WelcomeHandler(dialogue)
    habit = HabitHandler(presenter)
    ending = EndingHandler(welcome,
                           DailySummaryAggregator(data_store, habits),
                           DailyReportRenderer())
    handlers_by_class: Dict[str, StateHandler] = {
        "WelcomeHandler": welcome,
        "SubjectChoiceHandler": SubjectChoiceHandler(presenter, habit),
        "LearningTaskHandler": LearningTaskHandler(presenter),
        "AnsweringHandler": AnsweringHandler(presenter, rest_notice),
        "RewardHandler": RewardHandler(presenter, habit, ending),
        "HabitHandler": habit,
        "RestHandler": RestHandler(presenter, habit, ending, rest_notice, dialogue),
        "EndingHandler": ending,
    }
    registry = HandlerRegistry.from_graph(graph, handlers_by_class)
    return ConversationRouter(registry, default_guards(ending, rest_notice))
