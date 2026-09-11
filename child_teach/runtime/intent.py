# -*- coding: utf-8 -*-
"""意图识别：把孩子的一句话翻译成结构化意图。

这是「自然语言 → 工作流事件」的唯一入口，把关键词表集中在一个类里，
状态处理器因此不需要再关心字符串匹配。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from .. import config, safety

# --------------------------------------------------------------------------- #
# 关键词表
# --------------------------------------------------------------------------- #
MENU_DIGITS: Dict[str, str] = {
    "1": config.SUBJECT_CHINESE,
    "2": config.SUBJECT_MATH,
    "3": config.SUBJECT_ENGLISH,
    "4": config.SUBJECT_HABIT,
}
END_WORDS = ("结束", "不学了", "再见", "拜拜", "今天到这里", "到这里", "不玩", "不做了")
START_WORDS = ("开始", "你好", "小星", "再来一次", "hi", "hello", "嗨")
ACK_WORDS = ("好", "好的", "好啦", "嗯", "可以", "可以了", "行", "ok", "继续",
             "准备好了", "休息好了", "回来了", "还要", "还想")
CONTINUE_WORDS = ("继续", "再玩", "再来", "还要", "还想", "接着", "再来一组")
SWITCH_WORDS = ("换", "别的", "其他", "改")
REST_WORDS = ("休息", "歇", "累")
NEGATIVE_WORDS = ("还没", "没有", "没做", "没", "否", "不", "no", "nope", "下次")
POSITIVE_WORDS = ("是", "嗯", "做到", "做了", "有", "yes", "y")
ACK_MARKERS = ("好啦", "好了", "继续", "休息好", "可以了", "嗯")


@dataclass(frozen=True)
class Intent:
    """一句话的结构化解读。"""

    raw: str
    emotion: Optional[str] = None       # sensitive / resistance / None
    is_help: bool = False               # 「我不会」= 求助
    is_end: bool = False
    is_start: bool = False
    is_ack: bool = False                # 好 / 嗯 / 可以 / 继续
    is_continue: bool = False           # 再玩一组
    is_switch: bool = False             # 换科目
    is_rest: bool = False               # 想休息
    subject: Optional[str] = None       # 识别出的科目标识
    kind: str = "answer"                # 主分类（日志/调试用）
    tags: tuple = field(default_factory=tuple)

    # ------------------------------------------------------------ 便捷判断
    @property
    def is_empty(self) -> bool:
        return not self.raw

    @property
    def is_sensitive(self) -> bool:
        return self.emotion == "sensitive"

    @property
    def is_resistance(self) -> bool:
        return self.emotion == "resistance"

    @property
    def wants_habit(self) -> bool:
        return self.subject == config.SUBJECT_HABIT


class IntentClassifier:
    """规则式意图分类器（无需模型，零依赖、可解释、可审计）。"""

    def __init__(self) -> None:
        self.subject_keywords = config.subject_keyword_map()

    # ------------------------------------------------------------ 分类
    def classify(self, text: str) -> Intent:
        raw = self.normalize(text)
        emotion = safety.detect_emotion(raw)
        subject = self.parse_subject(raw)
        is_end = self.is_end(raw)
        flags = {
            "is_help": safety.is_help_request(raw),
            "is_start": self.is_start(raw),
            "is_ack": self.is_ack(raw),
            "is_continue": self.is_continue(raw),
            "is_switch": self.is_switch(raw),
            "is_rest": self.is_rest(raw),
            "subject": subject,
        }
        return Intent(raw=raw, emotion=emotion, is_end=is_end, kind=self._kind(
            raw, emotion, is_end, flags), **flags)

    def _kind(self, raw: str, emotion: Optional[str], is_end: bool, flags: dict) -> str:
        """给出一个主分类，方便日志排查（不参与业务判断）。"""
        if not raw:
            return "empty"
        if emotion == "sensitive":
            return "sensitive"
        if flags["is_help"]:
            return "help"
        if emotion == "resistance" and not is_end:
            return "resistance"
        if is_end:
            return "end"
        if flags["is_start"]:
            return "start"
        if flags["subject"]:
            return "subject"
        if flags["is_continue"]:
            return "continue"
        if flags["is_switch"]:
            return "switch"
        if flags["is_rest"]:
            return "rest"
        if flags["is_ack"]:
            return "ack"
        return "answer"

    # ------------------------------------------------------------ 单项判断
    @staticmethod
    def normalize(text: str) -> str:
        """去掉 BOM / 全角空格等噪声（语音与第三方前端常见）。"""
        return (text or "").replace("\ufeff", "").replace("\u3000", " ").strip()

    @staticmethod
    def is_end(text: str) -> bool:
        return any(word in text for word in END_WORDS)

    @staticmethod
    def is_start(text: str) -> bool:
        return any(word in text for word in START_WORDS)

    @staticmethod
    def is_continue(text: str) -> bool:
        return any(word in text for word in CONTINUE_WORDS)

    @staticmethod
    def is_switch(text: str) -> bool:
        return any(word in text for word in SWITCH_WORDS)

    @staticmethod
    def is_rest(text: str) -> bool:
        return any(word in text for word in REST_WORDS)

    @staticmethod
    def is_ack(text: str) -> bool:
        raw = text.strip().lower()
        return raw in {word.lower() for word in ACK_WORDS} or any(
            marker in raw for marker in ACK_MARKERS)

    @staticmethod
    def is_negative(text: str) -> bool:
        """习惯打卡用：判断孩子是否「还没做到」（不判错，只换引导）。"""
        raw = text.strip().lower()
        if raw in POSITIVE_WORDS:
            return False
        return any(word in raw for word in NEGATIVE_WORDS)

    def parse_subject(self, text: str) -> Optional[str]:
        """识别科目：支持数字菜单与自然说法（语文 / 拼音 / 算术 / 单词 / 小游戏…）。"""
        raw = text.strip()
        if raw in MENU_DIGITS:
            return MENU_DIGITS[raw]
        for keyword, subject in self.subject_keywords.items():
            if keyword in raw:
                return subject
        return None
