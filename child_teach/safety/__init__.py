# -*- coding: utf-8 -*-
"""安全边界包：题库审计（boundaries）、话术红线（language）、情绪识别（emotion）。

对外统一从这里导出，调用方只需 ``from child_teach import safety``。
"""
from .boundaries import audit_bank, check_question, extract_numbers
from .emotion import (HELP_WORDS, detect_emotion, is_help_request, looks_like_tired,
                      must_rest)
from .language import (PARENT_BANNED, audit_dialogue_templates, check_child_text,
                       check_parent_text, sanitize_child_text, sanitize_parent_text)

__all__ = [
    "check_question", "audit_bank", "extract_numbers",
    "check_child_text", "sanitize_child_text", "audit_dialogue_templates",
    "check_parent_text", "sanitize_parent_text", "PARENT_BANNED",
    "detect_emotion", "is_help_request", "looks_like_tired", "must_rest", "HELP_WORDS",
]
