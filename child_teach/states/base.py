# -*- coding: utf-8 -*-
"""处理器与守卫的抽象基类 + 结果构造小工具。

``StateHandler``  —— 一个工作流节点一个实现（状态模式：把「状态」变成对象）
``TurnGuard``     —— 每轮对话前的横切检查（责任链：安全 > 求助 > 抵触 > 结束）
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .. import safety
from ..runtime.context import TurnContext
from ..runtime.intent import Intent
from ..runtime.turn import TurnResult


# --------------------------------------------------------------------------- #
# 结果构造
# --------------------------------------------------------------------------- #
def result_from_lines(ctx: TurnContext, lines: List[str], note: Optional[str] = None,
                      meta: Optional[Dict[str, Any]] = None) -> TurnResult:
    """把若干行话术拼成一轮结果（统一过安全过滤）。"""
    text = "\n".join(line for line in lines if line)
    return TurnResult(
        child_text=safety.sanitize_child_text(text),
        state=ctx.state,
        state_path=ctx.state_path(),
        parent_note=note,
        meta=meta or {},
    )


def simple_result(ctx: TurnContext, text: str, note: Optional[str] = None,
                  meta: Optional[Dict[str, Any]] = None) -> TurnResult:
    return result_from_lines(ctx, [text], note=note, meta=meta)


# --------------------------------------------------------------------------- #
# 抽象基类
# --------------------------------------------------------------------------- #
class StateHandler(ABC):
    """工作流节点的处理器。"""

    #: 对应的节点名（由注册表校验，防止图与代码漂移）
    node: str = ""
    #: 类名（与工作流图 ``WorkflowNode.handler`` 字段对应）
    @classmethod
    def handler_name(cls) -> str:
        return cls.__name__

    @abstractmethod
    def handle(self, ctx: TurnContext, intent: Intent) -> TurnResult:
        """处理该状态下的一轮输入。"""

    # 允许子类复用的空实现（例如只做流转的节点）
    def describe(self) -> str:
        return f"{self.handler_name()}@{self.node or '未绑定'}"


class LaunchingHandler(StateHandler):
    """具备「开始一次学习单元」能力的节点（目前是欢迎页）。"""

    @abstractmethod
    def begin(self, ctx: TurnContext, reset_machine: bool = False) -> TurnResult:
        """启动（或重新启动）一次学习单元。"""


class TurnGuard(ABC):
    """横切守卫：在任何节点处理之前拦截一轮输入。"""

    #: 数值越小越先执行
    order: int = 100
    #: 守卫名称（调试与文档用）
    name: str = "guard"

    @abstractmethod
    def intercept(self, ctx: TurnContext, intent: Intent) -> Optional[TurnResult]:
        """返回结果表示已拦截；返回 None 表示放行给下一个守卫 / 节点处理器。"""

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name}(order={self.order})"
