# -*- coding: utf-8 -*-
"""冒烟测试：验证禁止行为被真正拦在代码里（不依赖 pytest，直接运行即可）。

运行方式：
    python -m unittest discover -s tests -v
或：
    python tests/test_agent.py
"""
from __future__ import annotations

import shutil
import sys
import unittest
import uuid
from datetime import datetime, timedelta  # noqa: F401
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from child_teach import config, safety  # noqa: E402
from child_teach.agent import ChildTutorAgent  # noqa: E402
from child_teach.dialogue import TEMPLATES  # noqa: E402
from child_teach.domain import Question  # noqa: E402
from child_teach.infra.clock import FrozenClock  # noqa: E402
from child_teach.repository import QuestionRepository, build_default_repository  # noqa: E402
from child_teach.runtime import (EV_TASK_READY, STATE_ANSWER, STATE_CHOOSE_SUBJECT,  # noqa: E402
                                 STATE_END, STATE_HABIT, STATE_REST, InvalidTransition,
                                 StateMachine, build_conversation_workflow)


class BaseCase(unittest.TestCase):
    """公共基类：每个用例使用独立的数据目录（放在工程内，避免系统临时目录权限问题）。"""

    TMP_ROOT = Path(__file__).resolve().parent / "_tmpdata"

    def setUp(self) -> None:
        self.data_dir = self.TMP_ROOT / uuid.uuid4().hex[:8]
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.clock = FrozenClock()

    def tearDown(self) -> None:
        shutil.rmtree(self.data_dir, ignore_errors=True)

    def new_agent(self, **kwargs) -> ChildTutorAgent:
        return ChildTutorAgent(data_dir=self.data_dir, clock=self.clock, **kwargs)


# --------------------------------------------------------------------------- #
# 1. 内容安全边界
# --------------------------------------------------------------------------- #
class TestSafetyBoundary(BaseCase):
    def test_builtin_bank_passes_audit(self):
        bank = build_default_repository()
        problems, total = bank.audit()
        self.assertGreaterEqual(total, 40, "内置题库样例太少")
        self.assertEqual(problems, [], f"题库存在超纲题目：{problems}")

    def test_dialogue_templates_have_no_banned_words(self):
        issues = safety.audit_dialogue_templates(TEMPLATES)
        self.assertEqual(issues, [], f"童趣话术触碰红线：{issues}")

    def test_out_of_scope_question_rejected(self):
        """100 以上计算题必须被拒绝入库。"""
        bank = QuestionRepository()
        bad = Question(qid="bad-1", subject="math", topic="add_sub_20", difficulty=1,
                       kind="fill", stem="100 + 200 等于几？", answer="300",
                       hint="数一数～", num_value="300")
        with self.assertRaises(ValueError):
            bank.add(bad)

    def test_multiplication_rejected(self):
        bank = QuestionRepository()
        bad = Question(qid="bad-2", subject="math", topic="add_sub_20", difficulty=1,
                       kind="fill", stem="3 乘法 4 等于几？", answer="12", hint="想一想～")
        with self.assertRaises(ValueError):
            bank.add(bad)

    def test_long_stem_rejected(self):
        bank = QuestionRepository()
        bad = Question(qid="bad-3", subject="chinese", topic="word", difficulty=1,
                       kind="fill", stem="这是一道" + "很长" * 40 + "的题目",
                       answer="x", hint="想一想～")
        with self.assertRaises(ValueError):
            bank.add(bad)

    def test_english_long_word_rejected(self):
        bank = QuestionRepository()
        bad = Question(qid="bad-4", subject="english", topic="animal", difficulty=1,
                       kind="fill", stem="跟读：hippopotamus", answer="", hint="慢慢读～")
        with self.assertRaises(ValueError):
            bank.add(bad)

    def test_sanitize_child_text(self):
        self.assertEqual(safety.sanitize_child_text("你错了"), "你差一点点啦")
        self.assertIn("再", safety.sanitize_child_text("这么简单都不会，真笨"))

    def test_emotion_detection(self):
        self.assertEqual(safety.detect_emotion("我不想学了"), "resistance")
        self.assertEqual(safety.detect_emotion("有人打我"), "sensitive")
        self.assertIsNone(safety.detect_emotion("3"))
        self.assertTrue(safety.is_help_request("我不会"))
        self.assertFalse(safety.is_help_request("7"))


# --------------------------------------------------------------------------- #
# 2. 状态机
# --------------------------------------------------------------------------- #
class TestStateMachine(BaseCase):
    def test_illegal_transition_rejected(self):
        sm = StateMachine(STATE_REST)
        with self.assertRaises(InvalidTransition):
            sm.fire(EV_TASK_READY, STATE_ANSWER)

    def test_legal_transition(self):
        sm = StateMachine(STATE_CHOOSE_SUBJECT)
        self.assertEqual(sm.fire("选择科目", "学习任务"), "学习任务")


# --------------------------------------------------------------------------- #
# 3. 答案判定
# --------------------------------------------------------------------------- #
class TestAnswerMatching(BaseCase):
    def test_loose_matching(self):
        q = Question(qid="t1", subject="math", topic="add_sub_10", difficulty=1,
                     kind="fill", stem="3+4=?", answer="7", accept=("七个", "7个"),
                     hint="数一数～", num_value="7")
        for raw in ("7", "七", "7个", "七个", " 7 ", "７"):
            self.assertEqual(q.matches(raw), (True, True), f"{raw} 应判对")

    def test_clock_variants(self):
        q = Question(qid="t2", subject="math", topic="clock", difficulty=2,
                     kind="fill", stem="几点？", answer="3点",
                     accept=("3:00", "三点", "3"), hint="看时针～", num_value="3")
        for raw in ("3点", "3:00", "三点", "3", "3点整"):
            self.assertTrue(q.matches(raw)[0], f"{raw} 应判对")

    def test_open_question_never_graded(self):
        q = Question(qid="t3", subject="chinese", topic="picture_talk", difficulty=2,
                     kind="open", stem="说说看～", hint="没有标准答案～")
        for raw in ("小花", "不知道", "随便"):
            self.assertEqual(q.matches(raw), (True, False))

    def test_check_kind_not_graded(self):
        q = Question(qid="t4", subject="habit", topic="tidy", difficulty=1,
                     kind="check", stem="收好了吗？", hint="慢慢来～")
        self.assertEqual(q.matches("收好了"), (True, False))
        self.assertEqual(q.matches("还没有"), (False, False))


# --------------------------------------------------------------------------- #
# 4. 学习主流程
# --------------------------------------------------------------------------- #
class TestLearningFlow(BaseCase):
    def test_welcome_and_menu(self):
        agent = self.new_agent()
        result = agent.start()
        self.assertIn(result.state, (STATE_CHOOSE_SUBJECT, "欢迎页"))
        self.assertIn("语文", agent.dialogue.menu())

    def test_round_has_at_most_three_questions(self):
        agent = self.new_agent()
        agent.start()
        result = agent.handle("数学")
        self.assertLessEqual(result.meta.get("total", 0), 3)
        for _ in range(6):
            q = agent.current_question
            if q is None:
                break
            result = agent.handle(q.answer or "好了")
            self.assertLessEqual(result.meta.get("total", 0), 3)

    def test_star_after_three_tasks(self):
        agent = self.new_agent()
        agent.start()
        agent.handle("数学")
        for _ in range(3):
            q = agent.current_question
            if q is None:
                break
            result = agent.handle(q.answer or "好了")
        self.assertGreaterEqual(agent.session.tasks, 3)
        self.assertGreaterEqual(agent.session.stars, 1)
        self.assertIn(config.STAR_EMOJI, result.child_text)
        self.assertGreaterEqual(int(agent.hub.profile.data["stars_total"]), 1)

    def test_fatigue_triggers_rest(self):
        """连续多次答错 → 自动跳转休息提醒（不强迫继续）。"""
        agent = self.new_agent()
        agent.start()
        agent.handle("数学")
        state = ""
        for _ in range(8):
            q = agent.current_question
            if q is None:
                break
            result = agent.handle("9")   # 数学题库中没有答案 9，必定答错
            state = result.state
            if state == STATE_REST:
                break
        self.assertEqual(state, STATE_REST)
        self.assertIn("休息", result.child_text)

    def test_ten_minutes_forces_rest(self):
        agent = self.new_agent()
        agent.start()
        self.clock.advance(10)
        result = agent.handle("数学")
        self.assertEqual(result.state, STATE_REST)
        self.assertEqual(result.meta.get("rest_reason"), "time")

    def test_wrong_answer_never_says_wrong(self):
        agent = self.new_agent()
        agent.start()
        agent.handle("语文")
        q = agent.current_question
        self.assertIsNotNone(q)
        result = agent.handle("~~~~")
        for bad in ("错了", "不对", "笨", "罚"):
            self.assertNotIn(bad, result.child_text)

    def test_resistance_switches_to_game(self):
        agent = self.new_agent()
        agent.start()
        agent.handle("数学")
        result = agent.handle("我不想学了")
        self.assertEqual(result.state, STATE_REST)
        self.assertIn("小游戏", result.child_text + agent.dialogue.say("resistance"))

    def test_sensitive_goes_to_parent(self):
        agent = self.new_agent()
        agent.start()
        result = agent.handle("有人打我")
        self.assertTrue(result.meta.get("sensitive"))
        self.assertIsNotNone(result.parent_note)
        self.assertTrue(agent.hub.profile.data["watchlist"])

    def test_finish_saves_record_and_parent_summary(self):
        agent = self.new_agent()
        agent.start()
        agent.handle("数学")
        for _ in range(3):
            q = agent.current_question
            if q is None:
                break
            agent.handle(q.answer or "好了")
        result = agent.handle("结束")
        self.assertTrue(result.finished)
        self.assertEqual(result.state, STATE_END)
        sessions = agent.hub.history.data["sessions"]
        self.assertEqual(len(sessions), 1)
        self.assertLessEqual(sessions[0]["minutes"], 15)
        self.assertIsNotNone(result.parent_note)
        self.assertIn("正确率", result.parent_note)

    def test_restart_after_end(self):
        agent = self.new_agent()
        agent.start()
        agent.handle("结束")
        result = agent.handle("开始")
        self.assertEqual(result.state, STATE_CHOOSE_SUBJECT)

    def test_all_child_text_is_safe(self):
        """全流程扫描：任何一句出口给孩子的话都不得触碰红线。"""
        agent = self.new_agent()
        outputs = [agent.start().child_text]
        for raw in ("数学", "9", "7", "，", "我不想学", "好啦", "小游戏", "坐姿棒棒的",
                    "做好了", "还没有", "结束", "开始", "语文", "abc"):
            result = agent.handle(raw)
            outputs.append(result.child_text)
            if result.parent_note:
                self.assertEqual(safety.check_parent_text(result.parent_note), [])
        for text in outputs:
            self.assertEqual(safety.check_child_text(text), [], f"不安全话术：{text}")

    def test_no_more_than_nine_questions_per_session(self):
        agent = self.new_agent()
        agent.start()
        for _ in range(30):
            if agent.current_question is None:
                agent.handle("1")
            q = agent.current_question
            if q is None:
                break
            agent.handle(q.answer or "好了")
            if agent.questions_presented >= config.MAX_QUESTIONS_PER_SESSION:
                break
        self.assertLessEqual(agent.questions_presented, config.MAX_QUESTIONS_PER_SESSION)


# --------------------------------------------------------------------------- #
# 5. 自适应难度
# --------------------------------------------------------------------------- #
class TestAdaptive(BaseCase):
    def test_level_up_and_down(self):
        agent = self.new_agent()
        bank = agent.bank
        question = bank.by_topic("math", "add_sub_10")[0]
        for _ in range(4):
            agent.adaptive.record_answer(question, True, True)
        self.assertGreaterEqual(agent.adaptive.level_for("math", "add_sub_10"), 2)

        other = bank.by_topic("math", "add_sub_20")[0]
        for _ in range(4):
            agent.adaptive.record_answer(other, False, True)
        self.assertLessEqual(agent.adaptive.level_for("math", "add_sub_20"), 2)

    def test_mastery_marks_topic(self):
        agent = self.new_agent()
        question = agent.bank.by_topic("chinese", "pinyin")[0]
        for _ in range(4):
            info = agent.adaptive.record_answer(question, True, True)
        self.assertTrue(agent.adaptive.is_mastered("chinese", "pinyin"))
        self.assertTrue(info["just_mastered"])

    def test_selection_avoids_mastered_and_respects_cap(self):
        agent = self.new_agent()
        for q in agent.bank.by_topic("math", "shape"):
            for _ in range(5):
                agent.adaptive.record_answer(q, True, True)
        picked = agent.adaptive.select("math", 10, agent.rng)
        self.assertLessEqual(len(picked), config.MAX_QUESTIONS_PER_ROUND)
        self.assertNotIn("shape", [q.topic for q in picked][:1])


# --------------------------------------------------------------------------- #
# 6. 习惯打卡与家长报告
# --------------------------------------------------------------------------- #
class TestHabitAndReport(BaseCase):
    def test_habit_checkin_flow(self):
        agent = self.new_agent()
        agent.start()
        result = agent.handle("习惯小游戏")
        self.assertEqual(result.state, STATE_HABIT)
        agent.handle("坐姿棒棒的")
        self.assertEqual(agent.habits.goal(), "坐姿棒棒的")
        for _ in range(3):
            result = agent.handle("做好啦")
        self.assertEqual(agent.habits.progress()["done"], 3)
        self.assertTrue(agent.habits.progress()["reached_goal"])

    def test_habit_not_done_is_not_punished(self):
        agent = self.new_agent()
        agent.start()
        agent.handle("习惯小游戏")
        result = agent.handle("坐姿棒棒的")
        result = agent.handle("还没有")
        self.assertEqual(safety.check_child_text(result.child_text), [])
        self.assertFalse(agent.habits.is_done("prep"))

    def test_parent_report_is_concise(self):
        agent = self.new_agent()
        agent.start()
        agent.handle("语文")
        for _ in range(3):
            q = agent.current_question
            if q is None:
                break
            agent.handle(q.answer or "好了")
        agent.handle("结束")
        report = agent.parent_summary()
        self.assertLessEqual(len(report.splitlines()), 5)
        self.assertIn("正确率", report)
        self.assertEqual(safety.check_parent_text(report), [])

    def test_parent_qa_answers_facts(self):
        agent = self.new_agent()
        agent.start()
        self.assertIn("暂无", agent.parent_ask("今天学了什么"))
        agent.handle("数学")
        q = agent.current_question
        if q is not None:
            agent.handle(q.answer or "好了")
        self.assertIn("正确率", agent.parent_ask("正确率多少"))

    def test_weekly_report(self):
        agent = self.new_agent()
        agent.habits.set_goal("坐姿棒棒的")
        for key in ("prep", "posture", "tidy"):
            agent.habits.check(key, True)
        report = agent.parent_weekly()
        self.assertIn("习惯", report)
        self.assertGreaterEqual(agent.habits.streak(), 1)


class TestWebService(BaseCase):
    """网页服务层（不开端口，直接测门面逻辑）。"""

    def test_payload_and_suggestions(self):
        from child_teach.webui import TutorService
        service = TutorService(data_dir=self.data_dir)
        payload = service.start()
        self.assertEqual(payload["suggestions"], ["语文", "数学", "英语", "习惯小游戏"])
        self.assertIn("小星老师", payload["child_text"])

        payload = service.say("数学")
        self.assertEqual(payload["status"]["state"], STATE_ANSWER)
        self.assertIn(payload["meta"]["kind"], ("choice", "fill"))
        self.assertTrue(payload["suggestions"])
        # 选择题：选项本身就是按钮，并额外给一个「我不会」
        if payload["meta"]["kind"] == "choice":
            self.assertEqual(payload["suggestions"][:-1], list(payload["meta"]["options"]))

    def test_hint_button_does_not_punish(self):
        from child_teach.webui import TutorService
        service = TutorService(data_dir=self.data_dir)
        service.start()
        service.say("数学")
        payload = service.say("我不会")
        self.assertEqual(safety.check_child_text(payload["child_text"]), [])
        self.assertTrue(payload["meta"].get("help"))

    def test_habit_endpoints(self):
        from child_teach.webui import TutorService
        service = TutorService(data_dir=self.data_dir)
        state = service.habit_state()
        self.assertEqual(len(state["items"]), 6)
        service.habit_goal("坐姿棒棒的")
        self.assertEqual(service.habit_state()["goal"], "坐姿棒棒的")
        for key in ("prep", "posture", "focus"):
            state = service.habit_check(key, True)
        self.assertEqual(state["progress"]["done"], 3)
        self.assertTrue(state["progress"]["reached_goal"])
        state = service.habit_check("prep", False)   # 可以撤销
        self.assertEqual(state["progress"]["done"], 2)

    def test_parent_endpoints(self):
        from child_teach.webui import TutorService
        service = TutorService(data_dir=self.data_dir)
        self.assertIn("暂无", service.parent_summary())
        self.assertIn("周报", service.parent_week())
        self.assertIn("建议", service.parent_advice())
        self.assertIn("题库 44 题", service.bank_report())

    def test_bank_report_flags_audit(self):
        from child_teach.webui import TutorService
        service = TutorService(data_dir=self.data_dir)
        report = service.bank_report()
        self.assertIn("全部通过安全审计", report)
        self.assertIn("无惩罚性/比较性表达", report)
        self.assertIn(f"数学上限 {config.MATH_MAX_NUMBER} 以内", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
