# -*- coding: utf-8 -*-
"""时钟抽象：把「时间从哪来」从业务逻辑里抽走。

好处：
    * 业务代码只依赖 ``Clock.now()``，不直接调用 ``datetime.now()``；
    * 测试与演示可以注入 ``FrozenClock``，把 10 分钟压缩成 0 秒，
      从而稳定验证「满 10 分钟强制休息」这类时长规则。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Callable, Optional


class Clock(ABC):
    """时钟接口。"""

    @abstractmethod
    def now(self) -> datetime:
        """当前时间。"""


class SystemClock(Clock):
    """真实系统时钟（生产默认值）。"""

    def now(self) -> datetime:
        return datetime.now()


class CallableClock(Clock):
    """把任意 ``() -> datetime`` 适配成 Clock（兼容旧的注入方式）。"""

    def __init__(self, source: Callable[[], datetime]) -> None:
        self._source = source

    def now(self) -> datetime:
        return self._source()


class FrozenClock(Clock):
    """可控时钟：测试与演示用，可手动推进时间。"""

    def __init__(self, start: Optional[datetime] = None) -> None:
        self._now = start or datetime.now()

    def now(self) -> datetime:
        return self._now

    def advance(self, minutes: float) -> datetime:
        self._now += timedelta(minutes=minutes)
        return self._now

    def set(self, moment: datetime) -> datetime:
        self._now = moment
        return self._now


def as_clock(source: Optional[object] = None) -> Clock:
    """把 None / Clock / 可调用对象统一成 Clock。"""
    if source is None:
        return SystemClock()
    if isinstance(source, Clock):
        return source
    if callable(source):
        return CallableClock(source)  # type: ignore[arg-type]
    raise TypeError(f"无法转换为 Clock：{source!r}")
