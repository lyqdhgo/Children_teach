# -*- coding: utf-8 -*-
"""题目领域对象：数据结构 + 答案判定 + 展示渲染。

不涉及题库检索（那是 ``repository`` 的职责），也不涉及安全审计
（那是 ``safety`` 的职责），本文件只回答一个问题：
**孩子这样回答，算不算对？**
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Dict, Optional, Tuple

# --------------------------------------------------------------------------- #
# 答案归一化（模块级纯函数，便于单测与复用）
# --------------------------------------------------------------------------- #
_PUNCT_RE = re.compile(r"[\s，。！？、,.!?~～…·「」“”\"'（）()：:；;\-—_]+")
_FW_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
_CN_DIGIT = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_RUN_RE = re.compile(r"[零一二两三四五六七八九十]+")
#: 比较时可忽略的量词/单位（仅当去掉后仍有内容时才忽略）
_UNIT_WORDS = ("个", "颗", "只", "元", "角", "分", "点", "时", "岁", "支",
               "本", "块", "辆", "朵", "张", "条", "整", "钟")

#: 不判对错的题型（朗读 / 跟读 / 看图说话）
OPEN_KINDS = ("read", "speak", "open")
#: 习惯自查题型
CHECK_KIND = "check"

_NEGATIVE_MARKERS = ("还没", "没有", "没做", "不会", "不想", "否", "no", "nope", "下次")


def _cn_num(token: str) -> Optional[int]:
    """中文数字串 → 整数，如 十三 → 13、二十 → 20。"""
    if not token:
        return None
    if token == "十":
        return 10
    if "十" in token:
        left, _, right = token.partition("十")
        tens = _CN_DIGIT.get(left, 1) if left else 1
        ones = _CN_DIGIT.get(right, 0) if right else 0
        return tens * 10 + ones
    if len(token) == 1:
        return _CN_DIGIT.get(token)
    return None


def loose_key(text: str) -> str:
    """宽松归一化：去标点空格、全角转半角、中文数字转阿拉伯数字、去量词。

    让「三个」「3 个」「3」都判定为同一个答案。
    """
    s = (text or "").strip().lower().translate(_FW_DIGITS)
    s = _PUNCT_RE.sub("", s)

    def repl(match: "re.Match[str]") -> str:
        value = _cn_num(match.group(0))
        return str(value) if value is not None else match.group(0)

    s = _CN_RUN_RE.sub(repl, s)
    stripped = s
    for unit in _UNIT_WORDS:
        stripped = stripped.replace(unit, "")
    return stripped or s


def first_int(text: str) -> Optional[int]:
    """取文本中第一个整数（支持中文数字）。"""
    def repl(match: "re.Match[str]") -> str:
        value = _cn_num(match.group(0))
        return str(value) if value is not None else match.group(0)

    s = _CN_RUN_RE.sub(repl, (text or "").translate(_FW_DIGITS))
    found = re.search(r"\d+", s)
    return int(found.group(0)) if found else None


# --------------------------------------------------------------------------- #
# 题目
# --------------------------------------------------------------------------- #
@dataclass
class Question:
    """一道小题（值对象）。"""

    qid: str
    subject: str
    topic: str
    difficulty: int
    stem: str
    answer: str = ""
    kind: str = "choice"
    options: Tuple[str, ...] = ()
    accept: Tuple[str, ...] = ()
    hint: str = ""             # 答错时的启发式提示（禁止直接否定）
    explanation: str = ""      # 温柔版讲解（第二次仍不会时给出）
    visual: str = ""           # 可视化/生活化描述（苹果、糖果、图形）
    read_aloud: str = ""       # 朗读提示（语文/英语）
    pinyin: Dict[str, str] = field(default_factory=dict)  # 生字 → 拼音
    num_value: str = ""        # 按数值比较（容错 3 / 3:00 / 三点）
    tags: Tuple[str, ...] = ()

    # ------------------------------------------------------------ 判定
    def matches(self, child_text: str) -> Tuple[bool, bool]:
        """判断孩子的回答，返回 ``(是否答对, 是否计分)``。

        ``计分=False`` 表示朗读 / 看图说话 / 习惯自查，不计入正确率。
        """
        raw = (child_text or "").strip()

        if self.kind in OPEN_KINDS:
            return True, False

        if self.kind == CHECK_KIND:
            done = bool(raw) and not any(m in raw.lower() for m in _NEGATIVE_MARKERS)
            return done, False

        keys = {loose_key(self.answer)}
        keys.update(loose_key(a) for a in self.accept)
        keys.discard("")
        if loose_key(raw) in keys:
            return True, True

        if self.num_value:
            got = first_int(raw)
            try:
                want: Optional[int] = int(self.num_value)
            except ValueError:
                want = None
            if got is not None and want is not None and got == want:
                return True, True

        return False, True

    # ------------------------------------------------------------ 序列化
    def to_dict(self) -> dict:
        data = asdict(self)
        for key in ("options", "accept", "tags"):
            data[key] = list(data[key])
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        payload = dict(data)
        for key in ("options", "accept", "tags"):
            value = payload.get(key)
            payload[key] = tuple(value) if value else ()
        payload.setdefault("pinyin", {})
        return cls(**payload)

    # ------------------------------------------------------------ 展示
    def display(self) -> str:
        """面向孩子的展示文本（含可视化、拼音、选项编号）。"""
        lines = [self.stem]
        if self.visual:
            lines.append(self.visual)
        if self.pinyin:
            pairs = "  ".join(f"{ch}({py})" for ch, py in self.pinyin.items())
            lines.append(f"💡 拼音小提示：{pairs}")
        if self.kind == "choice" and self.options:
            marks = "①②③④"
            lines.append("   ".join(f"{marks[i]} {opt}" for i, opt in enumerate(self.options)))
        elif self.read_aloud:
            lines.append(f"🔊 跟我读：{self.read_aloud}")
        return "\n".join(lines)
