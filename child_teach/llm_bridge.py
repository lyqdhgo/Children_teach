# -*- coding: utf-8 -*-
"""大模型接入桥：把 Agent 状态与系统提示词组装成 messages。

本模块默认不依赖任何第三方库（不会自动联网）：
    * 传入 ``client``（任何具有 ``chat(messages) -> str`` 方法的对象）时走真实模型；
    * 不传 ``client`` 时自动回退到 ``DialogueEngine`` 模板话术，
      因此整个应用在完全离线的情况下也能跑通。

安全约束（双保险）：
    * 送模型前：把时长 / 题量 / 内容边界写进 system 消息；
    * 模型返回后：再过一遍 ``safety.sanitize_child_text`` 或
      ``safety.sanitize_parent_text``，模型越界也不会说错话给孩子。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Protocol

from . import config, safety
from .dialogue import prompts as system_prompts
from .dialogue.engine import DialogueEngine


class ChatClient(Protocol):
    """最小模型客户端协议：实现 ``chat(messages) -> str`` 即可接入。"""

    def chat(self, messages: List[Dict[str, str]]) -> str:  # pragma: no cover
        ...


def _state_block(agent: Any) -> str:
    """把 Agent 当前状态压缩成一段结构化上下文，交给模型参考。"""
    status = agent.status() if hasattr(agent, "status") else {}
    question = getattr(agent, "current_question", None)
    payload: Dict[str, Any] = {
        "当前状态": status.get("state"),
        "本次学习已进行分钟": status.get("session_minutes"),
        "本休息周期内分钟": status.get("cycle_minutes"),
        "本次已出题数": status.get("questions_presented"),
        "连续答错次数": status.get("consecutive_wrong"),
        "累计星星": status.get("stars"),
        "当前科目": status.get("subject"),
    }
    if question is not None:
        payload["当前题目"] = {
            "题干": question.stem,
            "类型": question.kind,
            "难度": question.difficulty,
            "提示": question.hint,
        }
    habits = getattr(agent, "habits", None)
    if habits is not None:
        payload["今日习惯打卡"] = habits.progress()
    return "【运行时状态】\n" + json.dumps(payload, ensure_ascii=False, indent=2)


class LLMBridge:
    """对话模型的接入层（可插拔，默认离线回退）。"""

    def __init__(self, agent: Any, client: Optional[ChatClient] = None) -> None:
        self.agent = agent
        self.client = client
        self.fallback = DialogueEngine()

    # ------------------------------------------------------------ 组装消息
    def child_messages(self, user_text: str, history: Optional[List[Dict[str, str]]] = None
                       ) -> List[Dict[str, str]]:
        """面向孩子的消息列表（system 里嵌入硬性规则与当前状态）。"""
        system = system_prompts.child_dialogue_prompt(
            child_name=getattr(self.agent, "child_name", "小朋友"),
            extra=system_prompts.runtime_constraints(),
        )
        messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
        messages.append({"role": "system", "content": _state_block(self.agent)})
        for turn in (history or [])[-6:]:
            messages.append(turn)
        messages.append({"role": "user", "content": user_text})
        return messages

    def parent_messages(self, user_text: str) -> List[Dict[str, str]]:
        """面向家长的消息列表（第二套话术，客观简洁）。"""
        system = system_prompts.parent_report_prompt()
        facts = self.agent.parent_summary()
        return [
            {"role": "system", "content": system},
            {"role": "system", "content": "【今日数据】\n" + facts},
            {"role": "user", "content": user_text},
        ]

    # ------------------------------------------------------------ 调用
    def child_reply(self, user_text: str,
                    history: Optional[List[Dict[str, str]]] = None) -> str:
        """给孩子回话。没有 client 时用模板话术兜底。"""
        if self.client is None:
            return self.fallback.say("unknown")
        raw = self.client.chat(self.child_messages(user_text, history))
        return safety.sanitize_child_text(raw)

    def parent_reply(self, user_text: str) -> str:
        """给家长回话。没有 client 时走规则化数据问答。"""
        if self.client is None:
            return self.agent.parent_ask(user_text)
        raw = self.client.chat(self.parent_messages(user_text))
        return safety.sanitize_parent_text(raw)

    # ------------------------------------------------------------ 输出前校验
    @staticmethod
    def lint(text: str) -> Dict[str, Any]:
        """上线前自检：返回命中的禁止话术，便于打日志。"""
        return {
            "child_issues": safety.check_child_text(text),
            "parent_issues": safety.check_parent_text(text),
            "out_of_scope_numbers": [
                n for n in safety._extract_numbers(text)  # noqa: SLF001 (内部工具，自检用)
                if n > config.HARD_MAX_NUMBER
            ],
        }
