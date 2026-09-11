# -*- coding: utf-8 -*-
"""架构约束测试（fitness functions）：把「分层」和「别写在一个文件里」变成可执行断言。

四类检查：
    1. 体量约束：任何模块不得重新长成"上帝类/上帝文件"，``agent.py`` 必须是薄外观；
    2. 分层约束：依赖只能单向向下（domain ← repository ← states ← agent），禁止反向依赖；
    3. 工作流图约束：图结构合法、每个节点都绑定了处理器、缺绑定必须报错；
    4. 绑定一致性：节点名与处理器声明的节点名一致，防止复制粘贴出错。
"""
from __future__ import annotations

import ast
import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from child_teach import ChildTutorAgent  # noqa: E402
from child_teach.runtime import (STATE_ANSWER, STATE_CHOOSE_SUBJECT,  # noqa: E402
                                 STATE_END, STATE_ORDER, STATE_REST,
                                 build_conversation_workflow)
from child_teach.states import HandlerRegistry, build_router, default_guards  # noqa: E402

PACKAGE = Path(__file__).resolve().parent.parent / "child_teach"

#: 单文件行数上限（含注释与空行）。超过就说明该拆了。
MAX_MODULE_LINES = 240
#: 外观层上限：它只做装配，不该有业务逻辑
MAX_FACADE_LINES = 200

#: 分层允许的依赖方向（左 → 右表示"可以依赖"）
ALLOWED_LAYERS = {
    "config": set(),
    "domain": {"config", "domain"},
    "infra": {"config", "infra"},
    "safety": {"config", "safety"},
    "repository": {"config", "domain", "infra", "safety", "repository"},
    "dialogue": {"config", "domain", "safety", "dialogue"},
    "report": {"config", "domain", "infra", "safety", "report"},
    "runtime": {"config", "domain", "infra", "repository", "dialogue", "runtime"},
    "states": {"config", "domain", "infra", "safety", "dialogue", "repository",
               "report", "runtime", "states"},
    # 入站适配器（网页层）依赖应用门面，方向依然是"向下"
    "webui": {"agent", "config", "domain", "infra", "safety", "dialogue", "repository",
              "report", "runtime", "states", "webui"},
    # 组合根与入口可以依赖任意层
    "top": {"agent", "config", "dialogue", "domain", "infra", "llm_bridge", "report",
            "repository", "runtime", "safety", "states", "webui"},
}


def module_files() -> list:
    return sorted(path for path in PACKAGE.rglob("*.py") if "__pycache__" not in path.parts)


def layer_of(path: Path) -> str:
    """判断文件属于哪一层：包内目录 = 分层；根级模块 = 组合根（config 除外）。"""
    parts = path.relative_to(PACKAGE).parts
    if len(parts) == 1:
        name = parts[0].removesuffix(".py")
        return "config" if name == "config" else "top"
    return parts[0]


def imported_layers(path: Path) -> set:
    """解析该文件用相对导入引用了哪些"层"。"""
    rel = path.relative_to(PACKAGE)
    package_parts = list(rel.parts[:-1])          # 该文件所在包（相对包的路径）
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        base = package_parts[:len(package_parts) - (node.level - 1)] if node.level > 1 else package_parts
        module = (node.module or "").split(".")[0]
        target = base + ([module] if module else [])
        if target:
            found.add(target[0])
    return found


class TestModuleSize(unittest.TestCase):
    """1. 体量约束：一个类一个文件，文件不许重新膨胀。"""

    def test_no_module_exceeds_limit(self):
        offenders = []
        for path in module_files():
            lines = len(path.read_text(encoding="utf-8").splitlines())
            if lines > MAX_MODULE_LINES:
                offenders.append(f"{path.relative_to(PACKAGE)}（{lines} 行）")
        self.assertEqual(offenders, [],
                         f"以下模块超过 {MAX_MODULE_LINES} 行，请拆分：{offenders}")

    def test_agent_is_thin_facade(self):
        agent = PACKAGE / "agent.py"
        lines = len(agent.read_text(encoding="utf-8").splitlines())
        self.assertLess(lines, MAX_FACADE_LINES,
                        f"agent.py 又变成上帝类了（{lines} 行），请把逻辑放回 states/repository")

    def test_package_is_decomposed(self):
        """确认真的拆开了：模块数量与分层目录都要够。"""
        files = module_files()
        self.assertGreaterEqual(len(files), 40, "模块数量太少，说明还在堆大文件")
        relatives = [path.relative_to(PACKAGE) for path in files]
        subpackages = {rel.parts[0] for rel in relatives if len(rel.parts) > 1}
        for expected in ("domain", "infra", "safety", "repository", "dialogue",
                         "report", "runtime", "states", "webui"):
            self.assertIn(expected, subpackages, f"缺少分层目录：{expected}")


class TestLayering(unittest.TestCase):
    """2. 分层约束：依赖只能单向向下。"""

    def test_no_upward_dependency(self):
        violations = []
        for path in module_files():
            layer = layer_of(path)
            allowed = ALLOWED_LAYERS.get(layer)
            self.assertIsNotNone(allowed, f"未登记的分层：{layer}")
            for target in imported_layers(path):
                if target == layer or target in allowed:
                    continue
                violations.append(
                    f"{path.relative_to(PACKAGE)}（{layer}）→ {target}"
                )
        self.assertEqual(violations, [], "出现反向/越层依赖：\n" + "\n".join(violations))

    def test_domain_has_no_io(self):
        """领域层必须与框架无关：不得引用 infra / repository / states。"""
        for path in (PACKAGE / "domain").glob("*.py"):
            targets = imported_layers(path)
            self.assertFalse(targets & {"infra", "repository", "states", "webui"},
                             f"{path.name} 依赖了基础设施：{targets}")


class TestWorkflowGraph(unittest.TestCase):
    """3. 工作流图约束。"""

    def setUp(self):
        self.graph = build_conversation_workflow()

    def test_graph_is_valid(self):
        self.assertEqual(self.graph.validate(), [])

    def test_every_node_has_handler(self):
        for name, node in self.graph.nodes.items():
            self.assertTrue(node.handler, f"节点 {name} 没有绑定处理器")

    def test_safety_edges_exist_for_all_states(self):
        """任何"还会出题"的状态都能休息；任何状态都能结束（硬规则不可绕过）。"""
        for state in STATE_ORDER:
            if state not in (STATE_REST, STATE_END):
                self.assertIn(STATE_REST, self.graph.targets(state, "检测到疲劳"),
                              f"{state} 缺少疲劳兜底边")
            if state != STATE_END:
                self.assertIn(STATE_END, self.graph.targets(state, "结束学习"),
                              f"{state} 缺少结束兜底边")

    def test_rest_cannot_present_questions_directly(self):
        """在休息提醒里不许直接出题（必须先「休息结束」）。"""
        self.assertEqual(self.graph.targets(STATE_REST, "任务就绪"), set())

    def test_mermaid_and_ascii_render(self):
        mermaid = self.graph.to_mermaid()
        self.assertIn("flowchart", mermaid)
        self.assertIn("-.->", mermaid)          # 安全兜底边用虚线
        for name in STATE_ORDER:
            self.assertIn(self.graph.nodes[name].title, mermaid)
        self.assertIn("处理器", self.graph.to_ascii())

    def test_missing_handler_is_rejected(self):
        """图里加了节点却忘了写处理器 → 启动就该报错（防漂移）。"""
        graph = build_conversation_workflow()
        graph.add_node("新状态", "新状态", handler="NotImplementedHandler")
        with self.assertRaises(ValueError):
            HandlerRegistry.from_graph(graph, {})


class TestHandlerBinding(unittest.TestCase):
    """4. 绑定一致性：处理器声明的节点名必须与图中节点一致。"""

    def setUp(self) -> None:
        self.tmp = Path(__file__).resolve().parent / "_tmpdata" / uuid.uuid4().hex[:8]
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.agent = ChildTutorAgent(data_dir=self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_registry_covers_all_nodes(self):
        states = set(self.agent.router.registry.states())
        self.assertEqual(states, set(STATE_ORDER))

    def test_handler_node_names_match(self):
        for state, handler in self.agent.router.registry._handlers.items():  # noqa: SLF001
            self.assertEqual(handler.node, state,
                             f"{handler.handler_name()} 声明为 {handler.node}，却绑在 {state}")

    def test_guard_chain_order(self):
        orders = [guard.order for guard in self.agent.router.guards]
        self.assertEqual(orders, sorted(orders), "守卫链必须按 order 执行")
        names = [guard.name for guard in self.agent.router.guards]
        self.assertIn("敏感内容守卫", names)
        self.assertIn("结束守卫", names)

    def test_agent_architecture_is_self_describing(self):
        architecture = self.agent.architecture()
        self.assertEqual(architecture["validate"], [])
        self.assertIn("flowchart", architecture["mermaid"])
        self.assertEqual(len(architecture["handlers"]), len(STATE_ORDER))
        self.assertTrue(architecture["guards"])

    def test_router_build_is_pure_dependency_injection(self):
        """路由器可以脱离 Agent 单独组装（依赖注入可测）。"""
        router = build_router(self.agent.dialogue, self.agent.adaptive, self.agent.habits,
                              self.agent.data_store, self.agent.graph)
        self.assertEqual(set(router.registry.states()), set(STATE_ORDER))
        guards = default_guards(router.registry._handlers[STATE_END])  # noqa: SLF001
        self.assertEqual([g.order for g in guards], sorted(g.order for g in guards))

    def test_reset_returns_to_entry(self):
        self.agent.start()
        self.agent.handle("数学")
        self.assertNotEqual(self.agent.machine.state, STATE_CHOOSE_SUBJECT)
        self.agent.start()                       # 重新开始 = 重置到入口
        self.assertEqual(self.agent.machine.state, STATE_CHOOSE_SUBJECT)
        self.assertEqual(self.agent.ctx.session.tasks, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
