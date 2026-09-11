# -*- coding: utf-8 -*-
"""运行时层：对话轮次、意图识别、工作流图、状态机、运行上下文、奖励与记录。"""
from .turn import TurnResult
from .intent import Intent, IntentClassifier
from .workflow import WorkflowEdge, WorkflowGraph, WorkflowNode
from .conversation_graph import (EVENT_LABELS, EV_ANSWER_SUBMIT, EV_FATIGUE, EV_FINISH,
                                 EV_GREETED, EV_HABIT_DONE, EV_NEXT_ROUND, EV_PICK_HABIT,
                                 EV_PICK_SUBJECT, EV_REST_DONE, EV_RESTART, EV_ROUND_DONE,
                                 EV_SWITCH_SUBJECT, EV_TASK_READY, STATE_ANSWER,
                                 STATE_CHOOSE_SUBJECT, STATE_END, STATE_HABIT,
                                 STATE_LEARNING, STATE_ORDER, STATE_REWARD, STATE_REST,
                                 STATE_WELCOME, build_conversation_workflow)
from .state_machine import InvalidTransition, StateMachine
from .rewards import RewardService, StarRewardPolicy
from .recorder import SessionRecorder
from .context import TurnContext

__all__ = [
    "TurnResult", "Intent", "IntentClassifier",
    "WorkflowGraph", "WorkflowNode", "WorkflowEdge",
    "build_conversation_workflow", "STATE_ORDER", "EVENT_LABELS",
    "STATE_WELCOME", "STATE_CHOOSE_SUBJECT", "STATE_LEARNING", "STATE_ANSWER",
    "STATE_REWARD", "STATE_HABIT", "STATE_REST", "STATE_END",
    "EV_GREETED", "EV_PICK_SUBJECT", "EV_PICK_HABIT", "EV_TASK_READY",
    "EV_ANSWER_SUBMIT", "EV_ROUND_DONE", "EV_NEXT_ROUND", "EV_FATIGUE",
    "EV_REST_DONE", "EV_HABIT_DONE", "EV_SWITCH_SUBJECT", "EV_FINISH", "EV_RESTART",
    "StateMachine", "InvalidTransition",
    "StarRewardPolicy", "RewardService", "SessionRecorder", "TurnContext",
]
