# -*- coding: utf-8 -*-
"""本地 HTTP 服务：静态页面 + JSON 接口（标准库实现）。

    python main.py --web            # http://127.0.0.1:8765/
    python main.py --web --port 8899 --open

安全说明：只监听 127.0.0.1（本机），静态文件走白名单，孩子数据仍只写在本机 JSON。
"""
from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from ..domain.habit import HABIT_ITEMS
from .service import TutorService

WEB_DIR = Path(__file__).resolve().parent / "web"

#: 静态文件白名单：路径 → (文件名, MIME)
STATIC_FILES: Dict[str, tuple] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}

HABIT_KEYS = {item.key for item in HABIT_ITEMS}


class TutorHandler(BaseHTTPRequestHandler):
    """HTTP 处理：静态页面 + JSON 接口。"""

    server_version = "ChildTutorWeb/2.0"
    service: TutorService        # 由 create_server 注入

    # -------------------------------------------------------- 工具
    def _send(self, body: bytes, content_type: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: Any, code: int = 200) -> None:
        self._send(json.dumps(data, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8", code)

    def _error(self, code: int, message: str) -> None:
        self._json({"error": message}, code)

    def _static(self, path: str) -> None:
        entry = STATIC_FILES.get(path)
        if not entry:
            self._error(404, "not found")
            return
        filename, content_type = entry
        try:
            body = (WEB_DIR / filename).read_bytes()
        except OSError:
            self._error(500, f"缺少前端文件：{filename}")
            return
        self._send(body, content_type)

    def _body_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def log_message(self, fmt: str, *args) -> None:   # 静默，避免刷屏
        return

    # -------------------------------------------------------- GET
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path in STATIC_FILES:
                self._static(path)
            elif path == "/api/status":
                self._json({"status": self.service.status()})
            elif path == "/api/habit":
                self._json(self.service.habit_state())
            elif path == "/api/parent/summary":
                self._json({"report": self.service.parent_summary()})
            elif path == "/api/parent/week":
                self._json({"report": self.service.parent_week()})
            elif path == "/api/parent/advice":
                self._json({"report": self.service.parent_advice()})
            elif path == "/api/bank":
                self._json({"report": self.service.bank_report()})
            elif path == "/api/architecture":
                self._json(self.service.architecture())
            else:
                self._error(404, "not found")
        except Exception as exc:                      # noqa: BLE001 兜底，避免线程崩掉
            self._error(500, f"{type(exc).__name__}: {exc}")

    # -------------------------------------------------------- POST
    def do_POST(self) -> None:
        path = urlparse(self.path).path
        data = self._body_json()
        try:
            if path == "/api/start":
                self._json(self.service.start())
            elif path == "/api/say":
                self._json(self.service.say(str(data.get("text", ""))))
            elif path == "/api/habit/check":
                key = str(data.get("key", ""))
                if key not in HABIT_KEYS:
                    self._error(400, "未知打卡项")
                    return
                self._json(self.service.habit_check(key, bool(data.get("done"))))
            elif path == "/api/habit/goal":
                self._json(self.service.habit_goal(str(data.get("goal", ""))))
            elif path == "/api/parent/ask":
                self._json({"answer": self.service.parent_ask(str(data.get("query", "")))})
            else:
                self._error(404, "not found")
        except Exception as exc:                      # noqa: BLE001
            self._error(500, f"{type(exc).__name__}: {exc}")


def create_server(service: TutorService, host: str = "127.0.0.1",
                  port: int = 8765, tries: int = 20) -> ThreadingHTTPServer:
    """创建服务器；端口被占用时自动向后顺延。"""
    handler = type("BoundTutorHandler", (TutorHandler,), {"service": service})
    last_error: Optional[OSError] = None
    for offset in range(tries):
        try:
            httpd = ThreadingHTTPServer((host, port + offset), handler)
            httpd.daemon_threads = True
            return httpd
        except OSError as exc:
            last_error = exc
    raise OSError(f"端口 {port}~{port + tries - 1} 都被占用：{last_error}")


def run(data_dir: Optional[Path] = None, host: str = "127.0.0.1", port: int = 8765,
        child_name: str = "小朋友", open_browser: bool = False) -> None:
    """启动 Web 界面（阻塞运行，Ctrl+C 退出）。"""
    service = TutorService(data_dir=data_dir, child_name=child_name)
    httpd = create_server(service, host=host, port=port)
    actual_host, actual_port = httpd.server_address[:2]
    url = f"http://{actual_host}:{actual_port}/"

    print("=" * 62)
    print("🐣 小星老师 · 7 岁启蒙学习页面已启动")
    print(f"👉 请在浏览器打开：{url}")
    print(f"   数据目录：{service.agent.data_store.data_dir}")
    print(f"   孩子称呼：{service.agent.child_name}   （Ctrl+C 停止）")
    print("=" * 62)
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止服务。")
    finally:
        httpd.server_close()
