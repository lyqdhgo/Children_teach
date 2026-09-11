# -*- coding: utf-8 -*-
"""报告子系统：数据聚合（aggregator）、文本渲染（renderers）、家长问答（qa）。

与「面向孩子」的对话子系统完全隔离：这里只输出客观数据，不卖萌、不比较。
"""
from .aggregator import (DailySummaryAggregator, WeeklySummaryAggregator,
                         build_daily_summary, build_weekly_report)
from .renderers import DailyReportRenderer, WeeklyReportRenderer, render_daily, render_weekly
from .qa import ParentQAService, answer_parent_question

__all__ = [
    "DailySummaryAggregator", "WeeklySummaryAggregator",
    "build_daily_summary", "build_weekly_report",
    "DailyReportRenderer", "WeeklyReportRenderer", "render_daily", "render_weekly",
    "ParentQAService", "answer_parent_question",
]
