# -*- coding: utf-8 -*-
"""一轮对话的结果对象（值对象，供 CLI / Web / 语音端共用）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TurnResult:
    """一轮对话的输出。"""

    child_text: str                     # 给孩子看的话（已过安全过滤）
    state: str                          # 当前状态（工作流节点）
    state_path: List[str] = field(default_factory=list)   # 本轮经过的节点轨迹
    parent_note: Optional[str] = None   # 需要同步给家长的简报（如敏感内容、结束日报）
    finished: bool = False              # 本次学习是否已结束
    meta: Dict[str, Any] = field(default_factory=dict)    # 结构化元数据（UI/语音用）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "child_text": self.child_text,
            "state": self.state,
            "state_path": self.state_path,
            "parent_note": self.parent_note,
            "finished": self.finished,
            "meta": self.meta,
        }

    def with_state(self, state: str, state_path: List[str]) -> "TurnResult":
        """补全状态信息（由外观层统一回填）。"""
        self.state = state
        self.state_path = state_path
        self.finished = self.finished or state == "结束学习"
        return self
