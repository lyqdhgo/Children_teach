# -*- coding: utf-8 -*-
"""状态机：图驱动（graph-driven state machine）。

状态机不再自带一张硬编码的流转表，而是**读取工作流图**来校验流转，
因此「代码即架构图」：改图就是改流程，``--graph`` 导出的图永远和运行时一致。
"""
from __future__ import annotations

from typing import List, Optional, Set

from .conversation_graph import CONVERSATION_WORKFLOW, STATE_ORDER
from .workflow import WorkflowGraph, WorkflowPath


class InvalidTransition(RuntimeError):
    """非法状态流转（例如：在「休息提醒」里直接出题）。"""


class StateMachine:
    """带校验的有限状态机，内部由 ``WorkflowGraph`` 驱动。"""

    def __init__(self, graph: Optional[WorkflowGraph] = None,
                 initial: Optional[str] = None) -> None:
        # 友好重载：StateMachine("休息提醒") 等价于 StateMachine(initial="休息提醒")
        if isinstance(graph, str):
            graph, initial = None, graph
        self.graph = graph or CONVERSATION_WORKFLOW
        self.state = initial or self.graph.entry
        if self.state not in self.graph.nodes:
            raise ValueError(f"未知状态：{self.state}")
        self.path = WorkflowPath([self.state])
        self.events: List[str] = []

    # ------------------------------------------------------------ 查询
    def allowed_targets(self, event: str) -> Set[str]:
        return self.graph.targets(self.state, event)

    def can(self, event: str, target: Optional[str] = None) -> bool:
        targets = self.allowed_targets(event)
        if not targets:
            return False
        return target is None or target in targets

    def available_events(self) -> List[str]:
        """当前节点可用的事件（调试 / 文档用）。"""
        return self.graph.events(self.state)

    # ------------------------------------------------------------ 流转
    def reset(self, initial: Optional[str] = None) -> str:
        """重置到入口节点（重新开始一次学习单元）。"""
        self.state = initial or self.graph.entry
        self.path = WorkflowPath([self.state])
        self.events = []
        return self.state

    def fire(self, event: str, target: Optional[str] = None) -> str:
        """触发事件并流转；未指定 target 时要求目标唯一。"""
        targets = self.allowed_targets(event)
        if not targets:
            raise InvalidTransition(
                f"状态「{self.state}」不接受事件「{event}」"
                f"（可用事件：{self.graph.events(self.state)}）"
            )
        if target is None:
            if len(targets) > 1:
                raise InvalidTransition(
                    f"事件「{event}」有多个目标状态 {sorted(targets)}，需要显式指定"
                )
            target = next(iter(targets))
        if target not in targets:
            raise InvalidTransition(
                f"状态「{self.state}」+ 事件「{event}」不能到达「{target}」"
            )
        return self.force(target, event)

    def force(self, target: str, event: str = "强制跳转") -> str:
        """强制跳转（仅用于安全分支：疲劳休息、敏感内容、随时结束）。"""
        if target not in self.graph.nodes:
            raise ValueError(f"未知状态：{target}")
        self.state = target
        self.path.push(target)
        self.events.append(event)
        return self.state

    # ------------------------------------------------------------ 调试
    @property
    def history(self) -> List[str]:
        """完整节点轨迹（兼容旧属性名）。"""
        return list(self.path.nodes)

    def trace(self) -> str:
        """轨迹文本：欢迎页 -问候完成-> 选择科目。"""
        nodes = self.path.nodes
        if len(nodes) <= 1:
            return nodes[0] if nodes else ""
        parts = [nodes[0]]
        for index, event in enumerate(self.events):
            if index + 1 < len(nodes):
                parts.append(f"-{event}-> {nodes[index + 1]}")
        return " ".join(parts)

    def describe(self) -> str:
        return f"当前状态：{self.state}｜轨迹：{self.trace()}"


def state_order() -> List[str]:
    """节点定义的顺序（供文档与 CLI 使用）。"""
    return list(STATE_ORDER)
