# -*- coding: utf-8 -*-
"""奖励机制：星星发放策略 + 发放服务（策略模式）。

    StarRewardPolicy  什么时候该发星（纯规则，可单测）
    RewardService     发星、累加档案、生成童趣文案
"""
from __future__ import annotations

from .. import config
from ..infra import ProfileRepository


class StarRewardPolicy:
    """每完成 N 个小任务发 1 颗星（默认 3 个任务 1 颗）。"""

    def __init__(self, tasks_per_star: int = config.TASKS_PER_STAR) -> None:
        self.tasks_per_star = max(1, int(tasks_per_star))

    def should_award(self, task_count: int) -> bool:
        return task_count > 0 and task_count % self.tasks_per_star == 0

    def stars_for(self, task_count: int) -> int:
        return task_count // self.tasks_per_star


class RewardService:
    """按策略发星星，并返回给孩子的奖励话术（空字符串 = 本次不发）。"""

    def __init__(self, policy: StarRewardPolicy, profile: ProfileRepository) -> None:
        self.policy = policy
        self.profile = profile

    def grant_if_due(self, session, dialogue) -> str:
        """若达到发放条件则发放，并返回童趣文案。"""
        if session is None or not self.policy.should_award(session.tasks):
            return ""
        session.stars += 1
        total = self.profile.add_stars(1)
        return dialogue.star_award(session.tasks, total)
