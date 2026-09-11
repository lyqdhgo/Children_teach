# -*- coding: utf-8 -*-
"""工作流图引擎：节点 + 条件边 + 安全兜底边。

与「硬编码 if/elif 流转」相比，图带来三个好处：
    1. 结构可校验：孤立节点、不可达节点、重复边一眼可见（``validate()``）；
    2. 结构可导出：``to_mermaid()`` / ``to_ascii()`` 直接生成架构文档里的图，
       文档与代码不会漂移；
    3. 结构可扩展：新增一个状态只需加节点 + 边，不改任何已有处理器。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class WorkflowNode:
    """一个状态节点。"""

    name: str                 # 节点标识（也是状态名）
    title: str                # 展示标题
    handler: str = ""         # 绑定的处理器类名（文档用）
    description: str = ""
    terminal: bool = False    # 终止节点

    def __str__(self) -> str:  # pragma: no cover - 仅调试可读性
        return f"{self.title}[{self.handler or '-'}]"


@dataclass(frozen=True)
class WorkflowEdge:
    """一条带事件与条件的边。"""

    source: str
    target: str
    event: str
    condition: str = ""       # 触发条件说明（写进架构文档）
    safety: bool = False      # 是否为安全兜底边（疲劳 / 结束，任意状态可达）

    @property
    def label(self) -> str:
        return f"{self.event}｜{self.condition}" if self.condition else self.event


class WorkflowGraph:
    """有向图：节点表 + 边表，提供流转查询与图渲染。"""

    def __init__(self, name: str = "workflow") -> None:
        self.name = name
        self.nodes: Dict[str, WorkflowNode] = {}
        self.edges: List[WorkflowEdge] = []
        self._entry: Optional[str] = None

    # ------------------------------------------------------------ 构建
    def add_node(self, name: str, title: str = "", handler: str = "",
                 description: str = "", terminal: bool = False) -> WorkflowNode:
        node = WorkflowNode(name=name, title=title or name, handler=handler,
                            description=description, terminal=terminal)
        self.nodes[name] = node
        if self._entry is None:
            self._entry = name
        return node

    def add_edge(self, source: str, target: str, event: str,
                 condition: str = "", safety: bool = False) -> WorkflowEdge:
        edge = WorkflowEdge(source=source, target=target, event=event,
                            condition=condition, safety=safety)
        self.edges.append(edge)
        return edge

    # ------------------------------------------------------------ 查询
    @property
    def entry(self) -> str:
        return self._entry or ""

    def entry_name(self) -> str:
        return self.entry

    def node(self, name: str) -> WorkflowNode:
        return self.nodes[name]

    def terminals(self) -> List[WorkflowNode]:
        return [node for node in self.nodes.values() if node.terminal]

    def outgoing(self, source: str) -> List[WorkflowEdge]:
        return [edge for edge in self.edges if edge.source == source]

    def targets(self, source: str, event: str) -> Set[str]:
        """当前节点 + 事件 → 允许到达的节点集合（状态机据此校验）。"""
        return {edge.target for edge in self.edges
                if edge.source == source and edge.event == event}

    def events(self, source: str) -> List[str]:
        seen: List[str] = []
        for edge in self.outgoing(source):
            if edge.event not in seen:
                seen.append(edge.event)
        return seen

    # ------------------------------------------------------------ 校验
    def validate(self) -> List[str]:
        """返回结构问题列表（空 = 图健康）。"""
        problems: List[str] = []
        for edge in self.edges:
            if edge.source not in self.nodes:
                problems.append(f"边的起点不存在：{edge.source} -{edge.event}-> {edge.target}")
            if edge.target not in self.nodes:
                problems.append(f"边的终点不存在：{edge.source} -{edge.event}-> {edge.target}")

        seen_edges: Set[Tuple[str, str, str]] = set()
        for edge in self.edges:
            key = (edge.source, edge.event, edge.target)
            if key in seen_edges:
                problems.append(f"重复的边：{edge.source} -{edge.event}-> {edge.target}")
            seen_edges.add(key)

        reachable = self.reachable_from_entry()
        for name in self.nodes:
            if name not in reachable:
                problems.append(f"节点从入口不可达：{name}")
        for node in self.nodes.values():
            if not node.terminal and not self.outgoing(node.name):
                problems.append(f"非终止节点没有任何出边：{node.name}")
        return problems

    def reachable_from_entry(self) -> Set[str]:
        """从入口节点做一次广度优先遍历。"""
        if not self.entry:
            return set()
        visited: Set[str] = set()
        queue = [self.entry]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for edge in self.outgoing(current):
                if edge.target not in visited:
                    queue.append(edge.target)
        return visited

    # ------------------------------------------------------------ 渲染
    def _ids(self) -> Dict[str, str]:
        return {name: f"N{index}" for index, name in enumerate(self.nodes)}

    def to_mermaid(self, direction: str = "LR") -> str:
        """导出 Mermaid 流程图（可直接粘进 Markdown 架构文档）。"""
        ids = self._ids()
        lines = [f"flowchart {direction}"]
        for name, node in self.nodes.items():
            if node.terminal:
                lines.append(f'    {ids[name]}(["{node.title}"])')
            else:
                lines.append(f'    {ids[name]}["{node.title}"]')
        for edge in self.edges:
            arrow = "-.->" if edge.safety else "-->"
            label = edge.label.replace('"', "'")
            lines.append(f'    {ids[edge.source]} {arrow}|"{label}"| {ids[edge.target]}')
        return "\n".join(lines)

    def to_ascii(self) -> str:
        """导出纯文本版流转表（终端里看）。"""
        lines: List[str] = []
        for name, node in self.nodes.items():
            lines.append(f"[{node.title}]  处理器：{node.handler or '—'}"
                         + ("  （终止节点）" if node.terminal else ""))
            for edge in self.outgoing(name):
                mark = "  ~" if edge.safety else "  ├─"
                condition = f"（{edge.condition}）" if edge.condition else ""
                lines.append(f"{mark} {edge.event} → {self.nodes[edge.target].title}{condition}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "entry": self.entry,
            "nodes": [{"name": n.name, "title": n.title, "handler": n.handler,
                       "terminal": n.terminal, "description": n.description}
                      for n in self.nodes.values()],
            "edges": [{"source": e.source, "target": e.target, "event": e.event,
                       "condition": e.condition, "safety": e.safety}
                      for e in self.edges],
        }


@dataclass
class WorkflowPath:
    """一条流转轨迹（调试与现场追溯用）。"""

    nodes: List[str] = field(default_factory=list)

    def push(self, node: str) -> None:
        self.nodes.append(node)

    def describe(self, separator: str = " → ") -> str:
        return separator.join(self.dedupe())

    def dedupe(self) -> List[str]:
        out: List[str] = []
        for node in self.nodes:
            if not out or out[-1] != node:
                out.append(node)
        return out


def describe_graph(graph: WorkflowGraph) -> str:
    """给一份人类可读的图摘要（CLI ``--graph`` 用）。"""
    lines = [
        f"工作流：{graph.name}",
        f"节点 {len(graph.nodes)} 个｜边 {len(graph.edges)} 条｜入口："
        f"{graph.nodes[graph.entry].title if graph.entry else '—'}",
        "",
        graph.to_ascii(),
    ]
    problems = graph.validate()
    lines.append("")
    lines.append("✅ 图结构校验通过" if not problems else "❌ 图结构问题：\n" + "\n".join(problems))
    return "\n".join(lines)
