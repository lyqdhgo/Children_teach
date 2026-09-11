# -*- coding: utf-8 -*-
"""7 岁儿童启蒙教辅 Agent —— 命令行入口。

用法：
    python main.py                              交互式对话（孩子端，默认）
    python main.py --web [--port 8765]          启动可交互网页（浏览器打开链接）
    python main.py --demo                       自动演示：学习流程（奖励 / 休息规则）
    python main.py --demo-habit                 自动演示：习惯打卡流程
    python main.py --report [--day 2025-01-01]  打印家长简报（当日）
    python main.py --week                       打印家长周报
    python main.py --parent                     家长问答模式（交互）
    python main.py --audit                      安全审计：题库 + 话术红线
    python main.py --graph [--mermaid]          打印工作流图（架构设计）
    python main.py --prompt child|buddy|parent  打印系统提示词
    python main.py --data-dir D:\\path\\data      指定数据目录（默认 ./data）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 让 Windows 控制台也能正常输出中文与表情符号
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from child_teach import config  # noqa: E402
from child_teach.agent import ChildTutorAgent, TurnResult  # noqa: E402
from child_teach.dialogue import TEMPLATES  # noqa: E402
from child_teach.dialogue import prompts as system_prompts  # noqa: E402
from child_teach.domain.habit import HABIT_ITEMS  # noqa: E402
from child_teach.infra.clock import FrozenClock  # noqa: E402
from child_teach.repository import build_default_repository  # noqa: E402
from child_teach.runtime import STATE_HABIT, STATE_ORDER  # noqa: E402
from child_teach.runtime.workflow import describe_graph  # noqa: E402
from child_teach.safety import audit_dialogue_templates  # noqa: E402

LINE = "─" * 62


# --------------------------------------------------------------------------- #
# 输出工具
# --------------------------------------------------------------------------- #
def show(result: TurnResult, title: str = "") -> None:
    if title:
        print(f"\n{LINE}\n[{title}]  状态机：{' → '.join(result.state_path)}")
    print(f"\n🤖 小星老师：\n{result.child_text}")
    if result.parent_note:
        print(f"\n📋 给家长的简报：\n{result.parent_note}")


def build_agent(data_dir: Path, clock=None) -> ChildTutorAgent:
    return ChildTutorAgent(data_dir=data_dir, clock=clock)


# --------------------------------------------------------------------------- #
# 演示脚本
# --------------------------------------------------------------------------- #
def demo_learning(data_dir: Path) -> None:
    """演示学习主流程：出题 → 答错引导 → 星星奖励 → 10 分钟休息 → 结束总结。"""
    print(f"\n{LINE}\n【演示 1】学习流程：答错引导、星星奖励、10 分钟强制休息\n{LINE}")
    clock = FrozenClock()
    agent = build_agent(data_dir, clock=clock)
    show(agent.start(), "启动")

    show(agent.handle("数学"), "选择科目：数学")

    # 故意答错一次，展示「不否定、换方式启发」
    show(agent.handle("9"), "孩子答错（观察：是否只给启发，不说‘错’）")

    for step in range(3):
        question = agent.current_question
        if question is None:
            break
        show(agent.handle(question.answer or "好了"), f"孩子答对第 {step + 1} 题")

    # 让时钟快进 10 分钟 → 触发强制休息提醒
    clock.advance(10)
    show(agent.handle("1"), "再过一组（此时已学满 10 分钟，应强制休息）")
    show(agent.handle("好啦"), "休息结束，继续学习")

    question = agent.current_question
    if question is not None:
        show(agent.handle(question.answer or "好了"), "继续答题")

    result = agent.handle("结束")
    show(result, "结束学习")

    print(f"\n{LINE}\n📊 本次学习元数据：")
    meta = result.meta
    print(f"  时长 {meta.get('minutes')} 分钟｜任务 {meta.get('tasks')} 个｜"
          f"正确率 {int(float(meta.get('accuracy', 0)) * 100)}%｜星星 {meta.get('stars')} 颗")
    print(f"  状态轨迹：{meta.get('record', {}).get('state_trace')}")
    print(f"  数据目录：{agent.data_store.data_dir}")


def demo_habit(data_dir: Path) -> None:
    """演示习惯打卡：定目标 → 逐项打卡 → 正向鼓励 → 周报数据。"""
    print(f"\n{LINE}\n【演示 2】习惯打卡：每日小目标 + 6 项打卡 + 正向鼓励\n{LINE}")
    agent = build_agent(data_dir)
    show(agent.start(), "启动")
    show(agent.handle("习惯小游戏"), "进入习惯模块")
    show(agent.handle("坐姿棒棒的"), "设定今天的小目标")

    for index in range(len(HABIT_ITEMS)):
        result = agent.handle("做好啦")
        show(result, f"完成第 {index + 1} 项打卡")
        if result.state != STATE_HABIT:
            break

    print(f"\n{LINE}\n📋 家长周报（习惯部分）：\n{agent.parent_weekly()}")


# --------------------------------------------------------------------------- #
# 交互模式
# --------------------------------------------------------------------------- #
def interactive_child(data_dir: Path) -> None:
    agent = build_agent(data_dir)
    print(f"{LINE}\n🧒 孩子端对话模式（输入「退出」结束，输入「结束」结束本次学习）\n{LINE}")
    show(agent.start())
    while True:
        try:
            raw = input("\n👦 小朋友：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n（再见啦～）")
            break
        if raw in ("退出", "quit", "exit", "q"):
            print("👋 拜拜～明天见！")
            break
        if not raw:
            continue
        result = agent.handle(raw)
        show(result)
        if result.finished:
            print("\n（本次学习已结束。想看家长报告请退出后运行 --report，"
                  "或继续说「开始」重新开始。）")


def interactive_parent(data_dir: Path) -> None:
    agent = build_agent(data_dir)
    print(f"{LINE}\n👨‍👩‍👧 家长端问答（简洁客观；输入「退出」结束）\n{LINE}")
    print("\n例：今天学了什么 / 正确率多少 / 打卡了吗 / 建议 / 周报")
    while True:
        try:
            raw = input("\n👩 家长：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if raw in ("退出", "quit", "exit", "q", ""):
            break
        print(f"\n📋 报告：\n{agent.parent_ask(raw)}")


# --------------------------------------------------------------------------- #
# 审计与架构
# --------------------------------------------------------------------------- #
def run_audit() -> int:
    """安全审计：题库是否超纲 + 话术是否触碰红线。"""
    print(f"{LINE}\n🔍 安全审计\n{LINE}")
    repository = build_default_repository()
    problems, total = repository.audit()
    print(f"\n题库：共 {total} 题")
    if problems:
        for qid, issues in problems:
            print(f"  ❌ {qid}: {'；'.join(issues)}")
    else:
        print("  ✅ 全部通过：无超纲内容、无长句、无超量选项")

    issues = audit_dialogue_templates(TEMPLATES)
    print("\n童趣话术模板：")
    if issues:
        for path, hits in issues:
            print(f"  ❌ {path}: {'；'.join(hits)}")
    else:
        print(f"  ✅ 全部通过：{len(TEMPLATES)} 组话术无惩罚性/比较性表达")

    print("\n题库统计：")
    for name, stat in repository.stats().items():
        print(f"  {name}：{stat['题量']} 题 / {stat['知识点']} 个知识点 / "
              f"难度分布 {stat['难度分布']}")

    print(f"\n边界值：单次最多 {config.MAX_QUESTIONS_PER_ROUND} 题｜"
          f"单元上限 {config.MAX_QUESTIONS_PER_SESSION} 题｜"
          f"学习 {config.UNIT_MINUTES} 分钟强制休息｜"
          f"数学上限 {config.MATH_MAX_NUMBER} 以内")
    return 1 if (problems or issues) else 0


def run_graph(mermaid_only: bool = False) -> int:
    """打印工作流图：节点、条件边、处理器绑定与结构校验结果（不触碰孩子数据）。"""
    from child_teach.runtime import build_conversation_workflow
    from child_teach.states.guards import (EndRequestGuard, HelpGuard, ResistanceGuard,
                                           SensitiveGuard)

    graph = build_conversation_workflow()
    print(f"{LINE}\n🧭 工作流架构（代码即架构图）\n{LINE}\n")
    if not mermaid_only:
        print(describe_graph(graph))
        print(f"\n{LINE}\n节点 → 处理器绑定：")
        for name in STATE_ORDER:
            node = graph.nodes[name]
            print(f"  {node.title}  →  {node.handler}")
        print("\n守卫链（每轮先过守卫，再进节点处理器）：")
        for guard in sorted((SensitiveGuard, HelpGuard, ResistanceGuard, EndRequestGuard),
                            key=lambda cls: cls.order):
            print(f"  {guard.order:>3}. {guard.name}")

    print(f"\n{LINE}\nMermaid 图（可粘进 Markdown 文档）：\n")
    print("```mermaid")
    print(graph.to_mermaid())
    print("```")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="7 岁儿童启蒙教辅 Agent（后端）")
    parser.add_argument("--data-dir", type=Path, default=config.DATA_DIR,
                        help="数据目录（默认 ./data）")
    parser.add_argument("--demo", action="store_true", help="演示学习流程")
    parser.add_argument("--demo-habit", action="store_true", help="演示习惯打卡")
    parser.add_argument("--report", action="store_true", help="打印家长简报")
    parser.add_argument("--week", action="store_true", help="打印家长周报")
    parser.add_argument("--parent", action="store_true", help="家长问答模式")
    parser.add_argument("--audit", action="store_true", help="安全审计")
    parser.add_argument("--graph", action="store_true", help="打印工作流图")
    parser.add_argument("--mermaid", action="store_true", help="只输出 Mermaid 图")
    parser.add_argument("--web", action="store_true", help="启动可交互网页界面")
    parser.add_argument("--host", default="127.0.0.1", help="网页监听地址（默认仅本机）")
    parser.add_argument("--port", type=int, default=8765, help="网页端口（默认 8765）")
    parser.add_argument("--name", default=None, help="孩子称呼（默认读取档案）")
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    parser.add_argument("--prompt", choices=["child", "buddy", "parent"],
                        help="打印系统提示词")
    parser.add_argument("--day", default=None, help="指定日期 YYYY-MM-DD")
    args = parser.parse_args(argv)

    if args.audit:
        return run_audit()
    if args.graph or args.mermaid:
        return run_graph(mermaid_only=args.mermaid)

    if args.web:
        from child_teach.webui import run as run_web
        # 传 "小朋友" 时不会覆盖档案里已保存的称呼
        run_web(data_dir=args.data_dir, host=args.host, port=args.port,
                child_name=args.name or "小朋友", open_browser=args.open)
        return 0

    if args.prompt:
        name = {"child": "child_dialogue", "buddy": "learning_buddy",
                "parent": "parent_report"}[args.prompt]
        print(system_prompts.load(name))
        return 0

    agent = build_agent(args.data_dir)

    if args.report:
        print(agent.parent_summary(args.day))
        return 0
    if args.week:
        print(agent.parent_weekly(args.day))
        return 0
    if args.demo:
        demo_learning(args.data_dir)
        return 0
    if args.demo_habit:
        demo_habit(args.data_dir)
        return 0
    if args.parent:
        interactive_parent(args.data_dir)
        return 0

    interactive_child(args.data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
