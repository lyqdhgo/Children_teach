# -*- coding: utf-8 -*-
"""一个孩子的全部本地数据（组合三个物理文件，供组合根使用）。

    data/profile.json            孩子档案 / 星星 / 知识点掌握度
    data/learning_history.json   学习记录流水
    data/habit_log.json          习惯打卡日志
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .history_repository import HistoryRepository
from .profile_repository import ProfileRepository, default_profile
from .storage import JsonStore


class ChildDataStore:
    """组合根：把档案、流水、打卡三个仓储打包成一个对象。"""

    PROFILE_FILE = "profile.json"
    HISTORY_FILE = "learning_history.json"
    HABIT_FILE = "habit_log.json"

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.profile = ProfileRepository(
            JsonStore(self.data_dir / self.PROFILE_FILE, default_profile())
        )
        self.history = HistoryRepository(
            JsonStore(self.data_dir / self.HISTORY_FILE, {"sessions": []})
        )
        self.habits = JsonStore(self.data_dir / self.HABIT_FILE, {"days": {}})

    # ---------------------------------------------------------------- 便捷方法
    def save_all(self) -> None:
        self.profile.save()
        self.history.store.save()
        self.habits.save()

    def append_session(self, record: Dict[str, Any]) -> None:
        self.history.append(record)

    def sessions_on(self, day: str) -> List[dict]:
        return self.history.sessions_on(day)

    def sessions_between(self, start_day: str, end_day: str) -> List[dict]:
        return self.history.sessions_between(start_day, end_day)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ChildDataStore {self.data_dir}>"


#: 兼容旧名字
DataHub = ChildDataStore

__all__ = ["ChildDataStore", "DataHub", "ProfileRepository", "HistoryRepository",
           "default_profile"]
