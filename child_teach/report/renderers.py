# -*- coding: utf-8 -*-
"""报告渲染器：把结构化数据变成 ≤5 行的家长文本。

只做「写文案」，所有数字都来自 aggregator，避免一处改两处忘。
"""
from __future__ import annotations

from typing import Dict, List

from .. import config, safety
from .aggregator import subject_names


class DailyReportRenderer:
    """今日简报：第一行数据、第二行科目与重点、第三行打卡、第四行关注、第五行建议。"""

    def render(self, summary: Dict[str, object]) -> str:
        if summary["sessions"] == 0 and summary["habits_done"] == 0:
            return f"{summary['day']} 暂无学习记录。"

        lines: List[str] = [self.headline(summary)]

        topics = summary["topics"]
        if topics:
            detail = "、".join(
                "{label}({level})".format(
                    label=config.topic_label(str(t["subject"]), str(t["topic"])),
                    level=config.LEVEL_LABELS.get(int(t["level"]), int(t["level"])),
                )
                for t in sorted(topics, key=lambda x: -int(x["attempts"]))[:3]
            )
            lines.append(f"科目分布：{subject_names(summary['subject_count']) or '—'}；"
                         f"练习重点：{detail}")

        lines.append(
            "习惯打卡：{done}/{total} 项（连续 {streak} 天）{goal}".format(
                done=summary["habits_done"], total=summary["habits_total"],
                streak=summary["streak"],
                goal=f"；今日小目标：{summary['habit_goal']}" if summary["habit_goal"] else "",
            )
        )

        if summary["watchlist"]:
            lines.append(f"需关注：今日有 {len(summary['watchlist'])} 条情绪/敏感记录，"
                         f"建议温和沟通一次。")

        lines.append("建议：" + self.suggest(summary))
        return safety.sanitize_parent_text("\n".join(lines))

    @staticmethod
    def headline(summary: Dict[str, object]) -> str:
        assist = (f"（其中 {summary['assisted']} 题在提示后完成）"
                  if summary.get("assisted") else "")
        return ("{day} 学习 {minutes} 分钟｜完成 {questions} 题｜正确率 {acc}%｜"
                "新增星星 {stars} 颗{assist}").format(
            day=summary["day"], minutes=summary["minutes"], questions=summary["questions"],
            acc=int(float(summary["accuracy"]) * 100), stars=summary["stars"], assist=assist,
        )

    @staticmethod
    def suggest(summary: Dict[str, object]) -> str:
        """只给一条具体、可执行的建议。"""
        minutes = float(summary["minutes"])
        accuracy = float(summary["accuracy"])
        habits_done = int(summary["habits_done"])
        topics = summary["topics"]

        if summary["sessions"] == 0:
            return "今日未开始学习，可陪孩子花 8 分钟做一组小任务。"
        if minutes >= 20:
            return "今日单次学习偏长，建议拆成 2 段、每段 10 分钟内。"
        if topics and accuracy < 0.6:
            weak = max(topics, key=lambda t: int(t["attempts"]) - int(t["correct"]))
            return ("明天继续用生活道具（水果、积木）练「{}」，暂不升级难度。"
                    .format(config.topic_label(str(weak["subject"]), str(weak["topic"]))))
        if habits_done < 3:
            return "建议今晚选 1 项习惯（如整理文具）陪孩子完成并打卡。"
        if accuracy >= 0.85 and topics:
            return "掌握情况良好，明天可尝试挑战级题目各 1 道，仍控制单次 3 题以内。"
        return "保持每天 8～10 分钟节奏即可，无需加量。"


class WeeklyReportRenderer:
    """最近 7 天习惯与学习周报。"""

    def render(self, report: Dict[str, object]) -> str:
        habit = report["habits"]
        lines = [
            f"{report['start']} ~ {report['end']} 习惯与学习周报",
            "学习 {days} 天｜{minutes} 分钟｜{questions} 题｜正确率 {acc}%｜星星 {stars} 颗".format(
                days=report["study_days"], minutes=report["minutes"],
                questions=report["questions"],
                acc=int(float(report["accuracy"]) * 100), stars=report["stars"]),
            f"科目分布：{self._subject_line(report['by_subject'])}",
            "习惯达标 {q}/7 天｜累计打卡 {c} 次｜当前连续 {s} 天".format(
                q=habit["qualified_days"], c=habit["total_checks"], s=habit["current_streak"]),
            "习惯明细：" + "、".join(f"{k} {v}次" for k, v in habit["per_item"].items()),
        ]
        if report["mastered_topics"]:
            labels = [config.topic_label(t["subject"], t["topic"])
                      for t in report["mastered_topics"]]
            lines.append("已掌握知识点：" + "、".join(labels))
        if (habit.get("least_item") and habit["total_checks"]
                and min(habit["per_item"].values()) < max(habit["per_item"].values())):
            lines.append(f"建议：下周重点陪 1 项「{habit['least_item']}」，每天 1 分钟即可。")
        return safety.sanitize_parent_text("\n".join(lines))

    @staticmethod
    def _subject_line(by_subject: Dict[str, int]) -> str:
        text = "、".join(f"{config.SUBJECT_META[s]['name']}{n}次"
                        for s, n in by_subject.items() if s in config.SUBJECT_META)
        return text or "—"


# --------------------------------------------------------------------------- #
# 便捷函数（保持函数式调用可用）
# --------------------------------------------------------------------------- #
def render_daily(summary: Dict[str, object]) -> str:
    return DailyReportRenderer().render(summary)


def render_weekly(report: Dict[str, object]) -> str:
    return WeeklyReportRenderer().render(report)
