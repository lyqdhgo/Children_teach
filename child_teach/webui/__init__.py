# -*- coding: utf-8 -*-
"""本地网页界面包（标准库实现，无第三方依赖）。

    service.py  TutorService —— 线程安全的 Agent 门面（Web 层只跟它打交道）
    server.py   HTTP 处理与启动
    web/        前端页面（index.html / style.css / app.js）
"""
from .service import TutorService
from .server import TutorHandler, create_server, run

__all__ = ["TutorService", "TutorHandler", "create_server", "run"]
