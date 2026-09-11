# -*- coding: utf-8 -*-
"""孩子档案仓储：星星、知识点统计、题目作答记录、需关注清单。

业务代码不再直接操作 ``data["stars"] += 1`` 这类字典细节，
而是通过本类的方法，保证"改数据 + 落盘"永远成对出现。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .storage import JsonStore, now_iso


def default_profile() -> Dict[str, Any]:
    """孩子档案的初始结构。"""
    return {
        "child_name": "小朋友",
        "grade": 1,
        "age": 7,
        "stars": 0,          # 当前可用星星
        "stars_total": 0,    # 历史累计星星
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "topics": {},        # "subject/topic" -> 掌握度统计
        "seen": {},          # qid -> {"c": 对, "w": 错, "t": 最近作答时间}
        "settings": {
            "unit_minutes": 10,
            "max_questions_per_round": 3,
            "difficulty_cap": 3,
            "auto_break": True,
        },
        "watchlist": [],     # 需家长关注的事项（敏感话题 / 情绪记录）
    }


class ProfileRepository:
    """孩子档案仓储。"""

    def __init__(self, store: JsonStore) -> None:
        self.store = store

    # ---------------------------------------------------------------- 基础
    @property
    def data(self) -> Dict[str, Any]:
        return self.store.data

    def save(self) -> None:
        self.store.save()

    def touch(self) -> None:
        self.data["updated_at"] = now_iso()
        self.save()

    # ---------------------------------------------------------------- 称呼与设置
    @property
    def child_name(self) -> str:
        return str(self.data.get("child_name", "小朋友"))

    def set_child_name(self, name: str) -> None:
        self.data["child_name"] = name
        self.touch()

    @property
    def settings(self) -> Dict[str, Any]:
        return self.data.setdefault("settings", {})

    def difficulty_cap(self, fallback: int = 3) -> int:
        return int(self.settings.get("difficulty_cap", fallback))

    # ---------------------------------------------------------------- 星星
    @property
    def stars(self) -> int:
        return int(self.data.get("stars", 0))

    @property
    def stars_total(self) -> int:
        return int(self.data.get("stars_total", 0))

    def add_stars(self, count: int = 1) -> int:
        """加星星并落盘，返回当前可用星星数。"""
        self.data["stars"] = self.stars + count
        self.data["stars_total"] = self.stars_total + count
        self.touch()
        return self.stars

    # ---------------------------------------------------------------- 掌握度
    @property
    def topics(self) -> Dict[str, dict]:
        return self.data.setdefault("topics", {})

    @property
    def seen(self) -> Dict[str, dict]:
        return self.data.setdefault("seen", {})

    def seen_record(self, qid: str) -> Dict[str, Any]:
        return self.seen.setdefault(qid, {"c": 0, "w": 0})

    def mark_seen(self, qid: str, correct: bool) -> None:
        """记录某道题的作答历史（用于避免重复出已掌握的题）。"""
        record = self.seen_record(qid)
        key = "c" if correct else "w"
        record[key] = int(record.get(key, 0)) + 1
        record["t"] = now_iso()

    # ---------------------------------------------------------------- 需关注
    @property
    def watchlist(self) -> List[dict]:
        return self.data.setdefault("watchlist", [])

    def add_watch_item(self, item: Dict[str, Any]) -> None:
        """记录一条需家长关注的事项（情绪抵触 / 敏感内容）。"""
        self.watchlist.append(item)
        self.save()
