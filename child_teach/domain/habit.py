# -*- coding: utf-8 -*-
"""习惯打卡项（课前准备、坐姿、专注、按时收书、整理文具、阅读打卡）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

#: 当天完成 3 项以上即算「今天打卡成功」
DAY_GOAL_ITEMS = 3


@dataclass(frozen=True)
class HabitItem:
    """一个打卡项：家长侧名称 + 三种童趣话术。"""

    key: str
    label: str            # 家长侧名称
    child_prompt: str     # 面向孩子的童趣问法
    cheer_done: str       # 做到了的鼓励
    cheer_later: str      # 还没做的温和引导（不否定）


HABIT_ITEMS: Tuple[HabitItem, ...] = (
    HabitItem("prep", "课前准备",
              "上课前的准备做好了吗？课本、铅笔盒、水杯～",
              "哇，小书桌整整齐齐，你准备好了！⭐",
              "没关系呀，我们一起去把它们请出来～"),
    HabitItem("posture", "坐姿提醒",
              "小松树坐姿：头正、肩平、背直，做到了吗？",
              "背直直的真好看，像小松树一样！🌟",
              "我们慢慢来，小屁股坐满椅子就好啦～"),
    HabitItem("focus", "专注时长",
              "刚刚学习的时候，你有没有一直看着书本呀？",
              "你自己管住了小眼睛，太厉害啦！⭐",
              "下次我们试试看 3 分钟不分心，好不好？"),
    HabitItem("put_away", "按时收书",
              "时间到了，书本收起来了吗？",
              "说到做到，真棒！书本回家啦～⭐",
              "还有一点点时间，我们一起收，1、2、3～"),
    HabitItem("tidy", "整理文具",
              "铅笔、橡皮都送回文具盒了吗？",
              "文具们都回家啦，你真是小管家！🌟",
              "先送铅笔，再送橡皮，慢慢来哦～"),
    HabitItem("reading", "阅读打卡",
              "今天读了一本小书（或者一页小故事）吗？",
              "读了书的小朋友，脑袋里会开出小花哦！⭐",
              "今天没读也没关系，睡前我们一起看一页～"),
)

ITEMS_BY_KEY: Dict[str, HabitItem] = {item.key: item for item in HABIT_ITEMS}

HABIT_KEYS = tuple(item.key for item in HABIT_ITEMS)
