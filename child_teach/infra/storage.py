# -*- coding: utf-8 -*-
"""通用 JSON 文档存储（原子写 + 损坏自愈）与时间工具。

这里只有"怎么把 JSON 安全地存到磁盘"，不含任何孩子数据语义
（那些在 profile_repository / history_repository / child_data_store 里）。
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional


# --------------------------------------------------------------------------- #
# 时间工具
# --------------------------------------------------------------------------- #
def now_iso() -> str:
    """当前时间（秒级 ISO 字符串）。"""
    return datetime.now().replace(microsecond=0).isoformat()


def today_str() -> str:
    """今天日期 YYYY-MM-DD。"""
    return datetime.now().strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# 通用存储
# --------------------------------------------------------------------------- #
class JsonStore:
    """一个极简的 JSON 文档存储：先写临时文件再 os.replace，断电不会写坏数据。"""

    def __init__(self, path: Path, default: Optional[Dict[str, Any]] = None) -> None:
        self.path = Path(path)
        self.default = default if default is not None else {}
        self.data: Dict[str, Any] = {}
        self.load()

    # ---------------------------------------------------------------- 读写
    def load(self) -> Dict[str, Any]:
        """读取磁盘数据；文件不存在或损坏时回退到默认值（不抛异常）。"""
        if not self.path.exists():
            self.data = json.loads(json.dumps(self.default))
            self.save()
            return self.data
        try:
            with self.path.open("r", encoding="utf-8") as fp:
                loaded = json.load(fp)
            if not isinstance(loaded, dict):
                raise ValueError("顶层结构必须是对象")
            merged = json.loads(json.dumps(self.default))
            merged.update(loaded)
            self.data = merged
        except (json.JSONDecodeError, ValueError, OSError):
            # 数据损坏：备份后重建，保证程序始终可用
            self._backup()
            self.data = json.loads(json.dumps(self.default))
            self.save()
        return self.data

    def save(self) -> None:
        """原子写入。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.path.name + ".", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                json.dump(self.data, fp, ensure_ascii=False, indent=2)
            os.replace(tmp_name, self.path)
        finally:
            self._cleanup(tmp_name)

    def update(self, mutator: Callable[[Dict[str, Any]], Any]) -> Any:
        """修改并立即落盘。"""
        result = mutator(self.data)
        self.save()
        return result

    # ---------------------------------------------------------------- 内部
    def _backup(self) -> None:
        try:
            shutil.copy2(self.path, self.path.with_suffix(self.path.suffix + ".bak"))
        except OSError:
            pass

    @staticmethod
    def _cleanup(tmp_name: str) -> None:
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass

    def __repr__(self) -> str:  # pragma: no cover
        return f"<JsonStore {self.path.name} keys={list(self.data)[:4]}>"
