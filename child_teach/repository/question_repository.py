# -*- coding: utf-8 -*-
"""题库仓储：收录、检索、统计，并强制每道题过安全审计。

扩充题库有三种方式：
    1. ``repository.add(Question(...))``        代码内追加（超纲直接报错）
    2. ``repository.load_json(Path("x.json"))`` 外部 JSON 批量导入
    3. 提供自己的 ``Iterable[Question]`` 传给构造函数
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .. import config, safety
from ..domain.question import Question
from .seed_questions import SEED_QUESTIONS


class QuestionRepository:
    """题库容器（原 QuestionBank，职责不变，名字更贴合仓储语义）。"""

    def __init__(self, questions: Optional[Iterable[Question]] = None) -> None:
        self._items: Dict[str, Question] = {}
        if questions:
            self.add_many(questions)

    # ------------------------------------------------------------ 收录
    def add(self, question: Question) -> Question:
        """收录一道题；先过安全审计，违规直接拒绝入库。"""
        issues = safety.check_question(question)
        if issues:
            raise ValueError(
                f"题目 {question.qid} 未通过安全审计，禁止入库：{'；'.join(issues)}"
            )
        if question.qid in self._items:
            raise ValueError(f"题目 id 重复：{question.qid}")
        self._items[question.qid] = question
        return question

    def add_many(self, questions: Iterable[Question]) -> int:
        count = 0
        for question in questions:
            self.add(question)
            count += 1
        return count

    def load_json(self, path: Path) -> int:
        """从 JSON 文件批量导入题目（扩充接口）。"""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        items = data.get("questions", data) if isinstance(data, dict) else data
        return self.add_many(Question.from_dict(item) for item in items)

    def export_json(self, path: Path) -> None:
        payload = {"questions": [q.to_dict() for q in self._items.values()]}
        Path(path).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def extend(self, questions: Iterable[Question]) -> int:
        """插件式扩充入口。"""
        return self.add_many(questions)

    # ------------------------------------------------------------ 检索
    def __len__(self) -> int:
        return len(self._items)

    def all(self) -> List[Question]:
        return list(self._items.values())

    def get(self, qid: str) -> Optional[Question]:
        return self._items.get(qid)

    def by_subject(self, subject: str) -> List[Question]:
        return [q for q in self._items.values() if q.subject == subject]

    def by_topic(self, subject: str, topic: str) -> List[Question]:
        return [q for q in self._items.values()
                if q.subject == subject and q.topic == topic]

    def topics(self, subject: str) -> List[str]:
        seen: List[str] = []
        for question in self.by_subject(subject):
            if question.topic not in seen:
                seen.append(question.topic)
        return seen

    def topics_all(self) -> Dict[str, List[str]]:
        return {subject: self.topics(subject) for subject in config.SUBJECTS}

    # ------------------------------------------------------------ 统计与审计
    def stats(self) -> dict:
        result: Dict[str, dict] = {}
        for subject in config.SUBJECTS:
            items = self.by_subject(subject)
            by_difficulty: Dict[int, int] = {}
            for question in items:
                by_difficulty[question.difficulty] = by_difficulty.get(question.difficulty, 0) + 1
            result[config.SUBJECT_META[subject]["name"]] = {
                "题量": len(items),
                "知识点": len(self.topics(subject)),
                "难度分布": dict(sorted(by_difficulty.items())),
            }
        return result

    def audit(self) -> Tuple[List[Tuple[str, List[str]]], int]:
        """全库安全审计。"""
        return safety.audit_bank(self._items.values())


def build_default_repository() -> QuestionRepository:
    """内置样例题库（44 题，覆盖四大模块）。"""
    return QuestionRepository(SEED_QUESTIONS)
