# -*- coding: utf-8 -*-
"""习惯打卡仓储（原 HabitTracker）。

负责：每日小目标、逐项打卡、连续天数、周报数据。
只依赖 ``domain.habit`` 的打卡项定义与 ``infra`` 的 JsonStore。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence

from ..domain.habit import DAY_GOAL_ITEMS, HABIT_ITEMS, ITEMS_BY_KEY, HabitItem
from ..infra import JsonStore, now_iso, today_str


class HabitRepository:
    """习惯打卡存储与查询。"""

    def __init__(self, store: JsonStore) -> None:
        self.store = store

    # ------------------------------------------------------------ 基础读写
    def _days(self) -> Dict[str, dict]:
        return self.store.data.setdefault("days", {})

    def _day(self, day: Optional[str] = None) -> dict:
        day = day or today_str()
        return self._days().setdefault(
            day, {"goal": "", "items": {}, "created_at": now_iso()}
        )

    # ------------------------------------------------------------ 今日小目标
    def set_goal(self, text: str, day: Optional[str] = None) -> None:
        record = self._day(day)
        record["goal"] = (text or "").strip()[:30]
        record["goal_at"] = now_iso()
        self.store.save()

    def goal(self, day: Optional[str] = None) -> str:
        return str(self._day(day).get("goal", ""))

    # ------------------------------------------------------------ 打卡
    def check(self, key: str, done: bool, note: str = "",
              day: Optional[str] = None) -> dict:
        """记录一项打卡，返回打卡后的当日进度。"""
        if key not in ITEMS_BY_KEY:
            raise KeyError(f"未知打卡项：{key}")
        record = self._day(day)
        record.setdefault("items", {})[key] = {
            "done": bool(done), "at": now_iso(), "note": note[:60],
        }
        self.store.save()
        return self.progress(day)

    def is_done(self, key: str, day: Optional[str] = None) -> bool:
        return bool(self._day(day).get("items", {}).get(key, {}).get("done"))

    def day_items(self, day: Optional[str] = None) -> Dict[str, dict]:
        return dict(self._day(day).get("items", {}))

    def progress(self, day: Optional[str] = None) -> dict:
        """当日进度：已完成项 / 总项数 / 是否达标。"""
        items = self._day(day).get("items", {})
        done = [key for key, value in items.items() if value.get("done")]
        return {
            "day": day or today_str(),
            "done": len(done),
            "total": len(HABIT_ITEMS),
            "done_keys": done,
            "pending": [item.key for item in HABIT_ITEMS if item.key not in done],
            "reached_goal": len(done) >= DAY_GOAL_ITEMS,
        }

    def next_pending_item(self, exclude: Optional[Sequence[str]] = None,
                          day: Optional[str] = None) -> Optional[HabitItem]:
        """下一个待打卡项（一次只引导一件事）。"""
        skip = set(exclude or ())
        for item in HABIT_ITEMS:
            if item.key in skip or self.is_done(item.key, day):
                continue
            return item
        return None

    def count_done(self, day: Optional[str] = None) -> int:
        return self.progress(day)["done"]

    # ------------------------------------------------------------ 连续打卡
    def streak(self, end_day: Optional[str] = None) -> int:
        """连续达标天数（当天完成 ≥ DAY_GOAL_ITEMS 项即为达标）。"""
        cursor = datetime.strptime(end_day or today_str(), "%Y-%m-%d").date()
        days = self._days()
        streak = 0
        while True:
            key = cursor.strftime("%Y-%m-%d")
            record = days.get(key)
            done = sum(1 for value in (record or {}).get("items", {}).values()
                       if value.get("done"))
            if record and done >= DAY_GOAL_ITEMS:
                streak += 1
                cursor -= timedelta(days=1)
            else:
                break
        return streak

    # ------------------------------------------------------------ 周报告
    def weekly_report(self, end_day: Optional[str] = None) -> dict:
        """最近 7 天的习惯报告（面向家长，纯数据）。"""
        end = datetime.strptime(end_day or today_str(), "%Y-%m-%d").date()
        start = end - timedelta(days=6)
        days = self._days()

        per_item: Dict[str, int] = {item.key: 0 for item in HABIT_ITEMS}
        qualified_days = 0
        total_checks = 0
        daily: List[dict] = []

        for offset in range(7):
            day = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
            record = days.get(day, {})
            items = record.get("items", {})
            done = [key for key, value in items.items() if value.get("done")]
            for key in done:
                if key in per_item:
                    per_item[key] += 1
            total_checks += len(done)
            if len(done) >= DAY_GOAL_ITEMS:
                qualified_days += 1
            daily.append({"day": day, "done": len(done), "goal": record.get("goal", "")})

        best_key = max(per_item, key=lambda k: per_item[k]) if per_item else None
        weak_key = min(per_item, key=lambda k: per_item[k]) if per_item else None
        return {
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "qualified_days": qualified_days,
            "total_checks": total_checks,
            "per_item": {ITEMS_BY_KEY[k].label: v for k, v in per_item.items()},
            "best_item": ITEMS_BY_KEY[best_key].label if best_key and per_item[best_key] else None,
            "least_item": ITEMS_BY_KEY[weak_key].label if weak_key and per_item else None,
            "current_streak": self.streak(end_day),
            "daily": daily,
        }

    # ------------------------------------------------------------ 童趣进度话术
    def child_progress_text(self, day: Optional[str] = None) -> str:
        progress = self.progress(day)
        if progress["done"] == 0:
            return "今天我们还没打卡哦，一起来试试吧～"
        if progress["done"] >= progress["total"]:
            return f"哇，{progress['total']} 项全打卡啦！今天超级棒！🌟"
        return (f"已经打卡 {progress['done']} 项啦，"
                f"还有 {progress['total'] - progress['done']} 项，慢慢来～")
