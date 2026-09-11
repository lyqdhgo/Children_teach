# -*- coding: utf-8 -*-
"""学习记录流水仓储：每次学习单元的完整记录。"""
from __future__ import annotations

from typing import Any, Dict, List

from .storage import JsonStore


class HistoryRepository:
    """学习记录仓储（只追加，不改历史）。"""

    def __init__(self, store: JsonStore) -> None:
        self.store = store

    @property
    def data(self) -> Dict[str, Any]:
        return self.store.data

    def all_sessions(self) -> List[dict]:
        return list(self.store.data.get("sessions", []))

    def append(self, record: Dict[str, Any]) -> None:
        self.store.data.setdefault("sessions", []).append(record)
        self.store.save()

    def sessions_on(self, day: str) -> List[dict]:
        return [s for s in self.all_sessions() if s.get("date") == day]

    def sessions_between(self, start_day: str, end_day: str) -> List[dict]:
        return [s for s in self.all_sessions()
                if start_day <= str(s.get("date", "")) <= end_day]

    def count(self) -> int:
        return len(self.store.data.get("sessions", []))
