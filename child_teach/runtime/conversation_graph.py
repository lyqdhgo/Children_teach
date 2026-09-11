# -*- coding: utf-8 -*-
"""对话工作流图定义（本项目的"架构地图"）。

需求里给出的状态集合：
    欢迎页 → 选择科目 → 学习任务 → 答题交互 → 奖励反馈
                     ↘ 习惯打卡 ↗
    任意状态 → 休息提醒 / 结束学习

这里把它落成一张**显式有向图**：节点 = 状态 + 处理器，边 = 事件 + 触发条件。
``safety=True`` 的边是安全兜底边（疲劳强制休息、随时可结束），
它们保证「禁止长时间连续学习」「不强迫做题」这两条硬规则无法被绕过。
"""
from __future__ import annotations

from .workflow import WorkflowGraph

# --------------------------------------------------------------------------- #
# 状态常量（节点）
# --------------------------------------------------------------------------- #
STATE_WELCOME = "欢迎页"
STATE_CHOOSE_SUBJECT = "选择科目"
STATE_LEARNING = "学习任务"
STATE_ANSWER = "答题交互"
STATE_REWARD = "奖励反馈"
STATE_HABIT = "习惯打卡"
STATE_REST = "休息提醒"
STATE_END = "结束学习"

STATE_ORDER = [STATE_WELCOME, STATE_CHOOSE_SUBJECT, STATE_LEARNING, STATE_ANSWER,
               STATE_REWARD, STATE_HABIT, STATE_REST, STATE_END]

# --------------------------------------------------------------------------- #
# 事件常量（边）
# --------------------------------------------------------------------------- #
EV_GREETED = "问候完成"
EV_PICK_SUBJECT = "选择科目"
EV_PICK_HABIT = "选习惯游戏"
EV_TASK_READY = "任务就绪"
EV_ANSWER_SUBMIT = "提交答案"
EV_ROUND_DONE = "一组完成"
EV_NEXT_ROUND = "再来一组"
EV_FATIGUE = "检测到疲劳"
EV_REST_DONE = "休息结束"
EV_HABIT_DONE = "打卡结束"
EV_SWITCH_SUBJECT = "换科目"
EV_FINISH = "结束学习"
EV_RESTART = "重新开始"

#: 事件的中文说明（写进架构文档，避免读者猜）
EVENT_LABELS = {
    EV_GREETED: "启动后的问候与科目选择引导",
    EV_PICK_SUBJECT: "孩子选择了语文 / 数学 / 英语",
    EV_PICK_HABIT: "孩子选择了习惯小游戏",
    EV_TASK_READY: "题目已选好并呈现给孩子",
    EV_ANSWER_SUBMIT: "孩子提交答案，进入下一题",
    EV_ROUND_DONE: "本组 3 道小题全部作答完成",
    EV_NEXT_ROUND: "孩子还想再玩一组",
    EV_FATIGUE: "连续答错 ≥ 3 次，或本休息周期满 10 分钟",
    EV_REST_DONE: "休息结束，孩子选择继续",
    EV_HABIT_DONE: "6 项打卡引导结束",
    EV_SWITCH_SUBJECT: "孩子要求换科目",
    EV_FINISH: "孩子说结束，或题量/时长达到上限",
    EV_RESTART: "已结束后又说「开始」",
}


def build_conversation_workflow() -> WorkflowGraph:
    """构建对话工作流图（含安全兜底边）。"""
    graph = WorkflowGraph("7岁启蒙教辅对话工作流")

    graph.add_node(STATE_WELCOME, STATE_WELCOME, handler="WelcomeHandler",
                   description="问候 + 询问今天想学什么")
    graph.add_node(STATE_CHOOSE_SUBJECT, STATE_CHOOSE_SUBJECT, handler="SubjectChoiceHandler",
                   description="四大模块入口：语文 / 数学 / 英语 / 习惯小游戏")
    graph.add_node(STATE_LEARNING, STATE_LEARNING, handler="LearningTaskHandler",
                   description="按自适应难度选题（≤3 题）并呈现第一题")
    graph.add_node(STATE_ANSWER, STATE_ANSWER, handler="AnsweringHandler",
                   description="逐题作答、判定、引导与推进")
    graph.add_node(STATE_REWARD, STATE_REWARD, handler="RewardHandler",
                   description="每 3 个小任务发 1 颗星星，并询问下一步")
    graph.add_node(STATE_HABIT, STATE_HABIT, handler="HabitHandler",
                   description="每日小目标 + 6 项习惯打卡")
    graph.add_node(STATE_REST, STATE_REST, handler="RestHandler",
                   description="休息提醒（满 10 分钟 / 连续答错 / 孩子主动休息）")
    graph.add_node(STATE_END, STATE_END, handler="EndingHandler",
                   description="总结今日收获、落盘学习记录、生成家长简报", terminal=True)

    # ---------------- 主流程 ----------------
    graph.add_edge(STATE_WELCOME, STATE_CHOOSE_SUBJECT, EV_GREETED,
                   "启动 / 重新开始")
    graph.add_edge(STATE_CHOOSE_SUBJECT, STATE_LEARNING, EV_PICK_SUBJECT,
                   "剩余题量 > 0 且本周期 < 10 分钟")
    graph.add_edge(STATE_CHOOSE_SUBJECT, STATE_HABIT, EV_PICK_HABIT,
                   "孩子说「习惯小游戏」")
    graph.add_edge(STATE_LEARNING, STATE_ANSWER, EV_TASK_READY,
                   "已选出 1~3 题")
    graph.add_edge(STATE_ANSWER, STATE_ANSWER, EV_ANSWER_SUBMIT,
                   "本题已结束且本组还有下一题")
    graph.add_edge(STATE_ANSWER, STATE_REWARD, EV_ROUND_DONE,
                   "本组题目全部作答完成")
    graph.add_edge(STATE_REWARD, STATE_LEARNING, EV_NEXT_ROUND,
                   "孩子说「再玩一组」且未超单次题量上限")
    graph.add_edge(STATE_REWARD, STATE_CHOOSE_SUBJECT, EV_SWITCH_SUBJECT,
                   "孩子说「换个科目」")
    graph.add_edge(STATE_REWARD, STATE_HABIT, EV_PICK_HABIT,
                   "孩子说「小游戏」")
    graph.add_edge(STATE_HABIT, STATE_CHOOSE_SUBJECT, EV_HABIT_DONE,
                   "6 项打卡引导完成")
    graph.add_edge(STATE_HABIT, STATE_LEARNING, EV_HABIT_DONE,
                   "打卡过程中孩子直接说科目名")
    graph.add_edge(STATE_REST, STATE_ANSWER, EV_REST_DONE,
                   "休息后继续本组剩余的题")
    graph.add_edge(STATE_REST, STATE_LEARNING, EV_REST_DONE,
                   "休息后开始新的一组")
    graph.add_edge(STATE_REST, STATE_CHOOSE_SUBJECT, EV_REST_DONE,
                   "休息后重新选科目")
    graph.add_edge(STATE_REST, STATE_HABIT, EV_REST_DONE,
                   "休息后改玩习惯小游戏")
    graph.add_edge(STATE_END, STATE_WELCOME, EV_RESTART,
                   "孩子说「开始」")

    # ---------------- 安全兜底边（任意状态可达） ----------------
    # 「结束学习」是终止节点，不再出示任何题目，因此不需要疲劳兜底边
    for state in STATE_ORDER:
        if state not in (STATE_REST, STATE_END):
            graph.add_edge(state, STATE_REST, EV_FATIGUE,
                           "连续答错 ≥ 3 次 / 满 10 分钟 / 孩子说累了 / 情绪抵触",
                           safety=True)
        if state != STATE_END:
            graph.add_edge(state, STATE_END, EV_FINISH,
                           "孩子说「结束」，或达到题量/时长上限", safety=True)
    graph.add_edge(STATE_END, STATE_END, EV_FINISH, "已结束后再次收到结束指令",
                   safety=True)
    return graph


#: 全局唯一的对话工作流图（状态机与文档共用同一份定义）
CONVERSATION_WORKFLOW = build_conversation_workflow()
