# -*- coding: utf-8 -*-
"""全局配置：时长、题量、难度与「禁止行为」的硬性边界。

设计原则：
    所有与安全边界相关的数字与规则集中在本文件，业务代码只引用常量，
    不出现魔法数字。这样家长/老师想收紧或放宽限制时，只改这里即可。

Python 版本：3.9+（仅使用标准库）
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# 路径
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent.parent
PROMPT_DIR = BASE_DIR / "prompts"

#: 数据目录，可用环境变量 CT_DATA_DIR 覆盖（便于测试与多孩子隔离）
DATA_DIR = Path(os.environ.get("CT_DATA_DIR") or (BASE_DIR / "data"))

PROFILE_FILE = "profile.json"           # 孩子档案 + 星星 + 知识点掌握度
HISTORY_FILE = "learning_history.json"  # 学习记录流水
HABIT_FILE = "habit_log.json"           # 习惯打卡日志

# --------------------------------------------------------------------------- #
# 时长控制（禁止长时间连续学习）
# --------------------------------------------------------------------------- #
UNIT_MINUTES = 10            # 单次学习单元时长（分钟）
HARD_REST_MINUTES = 10       # 累计满 10 分钟 → 强制触发休息提醒，不再出新题
SOFT_REST_MINUTES = 8        # 满 8 分钟 → 温和预告「快该休息啦」
REST_SUGGEST_MINUTES = 2     # 建议休息时长（分钟）
REST_HINTS = (
    "站起来伸伸懒腰，像小猫一样～",
    "看看窗外最远的那棵树，眼睛会舒服哦～",
    "喝一小口水，咕嘟咕嘟～",
    "转转小脖子，左看看，右看看～",
)

# --------------------------------------------------------------------------- #
# 题量控制（禁止一次性输出大量题目）
# --------------------------------------------------------------------------- #
MAX_QUESTIONS_PER_ROUND = 3      # 单次最多 3 道小题（硬性上限）
MAX_QUESTIONS_PER_SESSION = 9    # 一个学习单元累计最多 9 题（3 组），防变相刷题
MAX_RETRY_PER_QUESTION = 1       # 每题最多提示 1 次，仍不会则温柔给答案
FATIGUE_WRONG_LIMIT = 3          # 连续答错达到该次数 → 自动休息

# --------------------------------------------------------------------------- #
# 奖励
# --------------------------------------------------------------------------- #
TASKS_PER_STAR = 3               # 每完成 3 个小任务 → 1 颗小星星
STAR_EMOJI = "⭐"

# --------------------------------------------------------------------------- #
# 难度与内容边界（禁止超纲）
# --------------------------------------------------------------------------- #
GRADE = 1                        # 一年级
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 3               # 1=基础 2=巩固 3=挑战（仍在一年级范围内）
START_DIFFICULTY = 1             # 首次学习从最基础的开始

#: 难度等级的中文名（难度引擎与家长报告共用，避免两处文案不一致）
LEVEL_LABELS = {1: "基础", 2: "巩固", 3: "挑战"}

MATH_MAX_NUMBER = 20             # 一年级（上）计算上限：20 以内
HARD_MAX_NUMBER = 100            # 全题库硬上限：任何题目不得出现 100 以上数字
CLOCK_NUMBER_LIMIT = 60          # 钟表题允许出现 60（分钟）
MONEY_NUMBER_LIMIT = 20          # 人民币题：20 元以内
MAX_STEM_CHARS = 60              # 单题题干长度上限，避免长句
MAX_OPTIONS = 4                  # 选项数量上限

#: 每个知识点的数字上限（用于安全审计；未列出则用 HARD_MAX_NUMBER）
TOPIC_NUMBER_LIMIT = {
    ("math", "add_sub_10"): 10,
    ("math", "add_sub_20"): MATH_MAX_NUMBER,
    ("math", "number_split"): MATH_MAX_NUMBER,
    ("math", "compare"): MATH_MAX_NUMBER,
    ("math", "clock"): CLOCK_NUMBER_LIMIT,
    ("math", "money"): MONEY_NUMBER_LIMIT,
    ("math", "shape"): 10,
    ("math", "pattern"): MATH_MAX_NUMBER,
    ("math", "word_problem"): MATH_MAX_NUMBER,
}

#: 超纲关键词（出现在题干中即判为超纲）
OUT_OF_SCOPE_KEYWORDS = (
    "乘法", "除法", "乘", "÷", "×", "*", "/", "平方", "分数", "小数",
    "方程", "负数", "时态", "语法", "从句", "过去式", "现在完成",
    "音标", "复数变化", "被动语态", "一元", "几何证明",
)

# --------------------------------------------------------------------------- #
# 科目定义
# --------------------------------------------------------------------------- #
SUBJECT_CHINESE = "chinese"
SUBJECT_MATH = "math"
SUBJECT_ENGLISH = "english"
SUBJECT_HABIT = "habit"

SUBJECTS = (SUBJECT_CHINESE, SUBJECT_MATH, SUBJECT_ENGLISH, SUBJECT_HABIT)

SUBJECT_META = {
    SUBJECT_CHINESE: {
        "name": "语文启蒙",
        "emoji": "📖",
        "menu_label": "语文（拼音·生字·古诗）",
        "child_intro": "我们一起来玩汉字和拼音吧～",
    },
    SUBJECT_MATH: {
        "name": "数学启蒙",
        "emoji": "🔢",
        "menu_label": "数学（加减·钟表·图形）",
        "child_intro": "我们来数一数、算一算，像玩游戏一样哦～",
    },
    SUBJECT_ENGLISH: {
        "name": "英语启蒙",
        "emoji": "🐣",
        "menu_label": "英语（单词·跟读）",
        "child_intro": "我们来说说好听的英文，跟着我读就好啦～",
    },
    SUBJECT_HABIT: {
        "name": "学习习惯",
        "emoji": "🌟",
        "menu_label": "习惯小游戏（坐姿·整理·阅读）",
        "child_intro": "我们来玩个轻松的小游戏，看看谁坐得最棒～",
    },
}

# --------------------------------------------------------------------------- #
# 情绪 / 敏感内容识别词
# --------------------------------------------------------------------------- #
RESISTANCE_WORDS = (
    "不想学", "不想做", "不学了", "不要学", "讨厌", "好难", "太难", "不会",
    "累", "烦", "无聊", "没意思", "不想", "不要", "走开", "别问了", "歇一会",
)

SENSITIVE_WORDS = (
    "打我", "被打", "欺负", "害怕", "恐怖", "流血", "死了", "自杀", "陌生人",
    "网友", "离家出走", "爸爸妈妈吵架", "离婚", "肚子疼", "头疼", "生病",
)

# --------------------------------------------------------------------------- #
# 面向孩子的语言红线（惩罚性 / 比较式 / 否定式）
# --------------------------------------------------------------------------- #
BANNED_CHILD_PHRASES = (
    "笨", "傻子", "真差", "太差", "又错", "错了", "不对", "不正确", "失败",
    "罚", "不许", "必须做完", "再做十", "别人", "比你", "比不上", "落后",
    "倒数", "倒数第一", "不听话", "不认真", "注意力差", "没用", "闭嘴",
)

#: 检出红线话术时的替换话术（按顺序匹配，具体的短语写在前面）
SOFT_REPLACEMENTS = {
    "这么简单都不会": "我们再试试",
    "真笨": "你已经很努力啦",
    "怎么这么笨": "我们慢慢来",
    "错了": "差一点点啦",
    "又错": "我们再看看",
    "不正确": "再试一次看看～",
    "不对": "我们再想一想哦",
    "不许": "我们可以",
    "必须做完": "做完就可以休息啦",
    "笨": "慢慢来",
    "罚": "陪",
    "比别人": "比昨天",
    "别人都会": "我们再试试",
    "比不上": "还在练习中",
}


def topic_limit(subject: str, topic: str) -> int:
    """返回某个知识点允许出现的最大数字。"""
    return TOPIC_NUMBER_LIMIT.get((subject, topic), HARD_MAX_NUMBER)


#: 知识点中文名（供家长报告与孩子总结使用，避免出现英文内部标识）
TOPIC_LABELS = {
    "chinese": {
        "pinyin": "拼音", "character": "生字认读", "word": "组词",
        "sentence": "短句朗读", "picture_talk": "看图说话", "poem": "古诗启蒙",
    },
    "math": {
        "add_sub_10": "10以内加减", "add_sub_20": "20以内加减",
        "number_split": "数的分与合", "compare": "比大小", "clock": "认识钟表",
        "money": "认识人民币", "shape": "认识图形", "pattern": "找规律",
        "word_problem": "生活应用题",
    },
    "english": {
        "animal": "动物单词", "color": "颜色单词", "number": "数字单词",
        "food": "食物单词", "sentence": "简单短句", "song": "英文儿歌",
    },
    "habit": {
        "prep": "课前准备", "posture": "坐姿", "focus": "专注",
        "tidy": "整理文具", "reading": "阅读打卡", "put_away": "按时收书",
    },
}


def topic_label(subject: str, topic: str) -> str:
    """知识点中文名；未知知识点回退为原标识。"""
    return TOPIC_LABELS.get(subject, {}).get(topic, topic)


def subject_name(subject: str) -> str:
    """科目中文名。"""
    return SUBJECT_META.get(subject, {}).get("name", subject)


def subject_keyword_map() -> dict:
    """孩子口语 → 科目标识 的映射（用于自然语言选择科目）。"""
    mapping = {
        "语文": SUBJECT_CHINESE, "拼音": SUBJECT_CHINESE, "汉字": SUBJECT_CHINESE,
        "生字": SUBJECT_CHINESE, "古诗": SUBJECT_CHINESE, "读课文": SUBJECT_CHINESE,
        "数学": SUBJECT_MATH, "算术": SUBJECT_MATH, "算数": SUBJECT_MATH,
        "计算": SUBJECT_MATH, "钟表": SUBJECT_MATH, "图形": SUBJECT_MATH,
        "英语": SUBJECT_ENGLISH, "英文": SUBJECT_ENGLISH, "单词": SUBJECT_ENGLISH,
        "习惯": SUBJECT_HABIT, "打卡": SUBJECT_HABIT, "小游戏": SUBJECT_HABIT,
        "游戏": SUBJECT_HABIT,
    }
    return mapping
