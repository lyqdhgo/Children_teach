# 7 岁儿童启蒙教辅 Agent（后端）

面向 **7 岁小学一年级** 孩子的启蒙学习 Agent，覆盖**语文 / 数学 / 英语 / 学习习惯**四大模块。
纯 Python 标准库实现（零第三方依赖），提供 CLI、可交互网页、家长报告三套入口。

> **架构设计详见 [`docs/architecture.md`](docs/architecture.md)** —— 工作流图、分层依赖、类图、时序图、扩展指南。
> 图由代码导出（`python main.py --graph`），不会与实现漂移。

设计前提（写进了代码规则，不只是文案）：

| 孩子特点 | 代码里的对应机制 |
| --- | --- |
| 注意力约 10 分钟 | 工作流图的**疲劳兜底边**：满 10 分钟强制进入「休息提醒」，停止出题 |
| 识字量有限 | 题干 ≤ 60 字；生字带拼音；朗读提示；选项配 emoji；网页端可语音朗读 |
| 讨厌枯燥刷题 | 单次最多 3 题、一个单元最多 9 题；每 3 个小任务 1 颗星星；不重复已掌握题目 |
| 答错会受挫 | 答错不否定：先启发，再不会才温柔给答案；全程无惩罚性/比较性话术 |

---

## 一、快速开始

```bash
# 0) 无需安装依赖（Python 3.9+，只用标准库）
python --version

# 1) 可交互网页（推荐）
python main.py --web                 # 浏览器打开 http://127.0.0.1:8765/
python main.py --web --port 8899 --open --name 朵朵

# 2) 看架构图（节点 / 条件边 / 处理器绑定 / 结构校验）
python main.py --graph
python main.py --mermaid             # 只导出 Mermaid，粘进文档或 Wiki

# 3) 安全审计：题库超纲 + 话术红线
python main.py --audit

# 4) 演示
python main.py --demo                # 学习流程（答错引导 / 星星 / 10 分钟强制休息）
python main.py --demo-habit          # 习惯打卡（目标 → 6 项 → 鼓励 → 周报）

# 5) 终端交互
python main.py                       # 孩子端
python main.py --parent              # 家长问答

# 6) 家长报告
python main.py --report              # 今日简报（≤5 行，客观数据）
python main.py --week                # 最近 7 天周报

# 7) 系统提示词
python main.py --prompt child        # 面向孩子的对话子 Agent
python main.py --prompt buddy        # 配套子 Agent（学习伙伴）
python main.py --prompt parent       # 面向家长的汇报 Agent

# 8) 测试：39 个行为测试 + 17 个架构约束测试
python -m unittest discover -s tests -v
```

---

## 二、代码结构（分层 + 单一职责）

```
Children_teach/
├─ main.py                    # CLI 入口：交互 / 网页 / 演示 / 审计 / 架构图
├─ docs/architecture.md       # 架构设计（工作流图 / 分层 / 类图 / 时序图 / 扩展指南）
├─ prompts/                   # 系统提示词（Markdown，可直接改文案）
│  ├─ child_dialogue_system_prompt.md
│  ├─ learning_buddy_prompt.md
│  └─ parent_report_prompt.md
├─ child_teach/
│  ├─ config.py               # 所有硬性边界：时长/题量/难度/红线词/知识点上限
│  ├─ agent.py                # 薄外观（159 行）：只做装配与两个对话接口
│  ├─ domain/                 # 领域对象：Question / Round / Session / HabitItem
│  ├─ infra/                  # 时钟 Clock、JsonStore、档案/流水仓储
│  ├─ safety/                 # boundaries 超纲审计 / language 话术红线 / emotion 情绪
│  ├─ repository/             # 题库（44 题样例数据独立成文件）、自适应难度、打卡仓储
│  ├─ dialogue/               # templates 话术数据 / engine 童趣引擎 / prompts 提示词
│  ├─ report/                 # aggregator 聚合 / renderers 渲染 / qa 家长问答
│  ├─ runtime/                # workflow 图引擎 / state_machine / context / intent / rewards / recorder
│  ├─ states/                 # 8 个状态处理器 + 4 个守卫 + 出题器 + 休息服务 + 路由器
│  └─ webui/                  # 本地网页服务（service + server + web/ 前端）
├─ tests/
│  ├─ test_agent.py           # 39 个行为测试（安全边界、状态流转、习惯、报告、网页服务）
│  └─ test_architecture.py    # 17 个架构约束测试（体量 / 分层 / 图 / 绑定）
└─ data/                      # 运行时生成：profile / learning_history / habit_log
```

### 一个类一个职责

| 关注点 | 归属 |
| --- | --- |
| 每个状态的规则 | `states/welcome.py`、`subject_choice.py`、`learning.py`、`answering.py`、`reward.py`、`habit.py`、`rest.py`、`ending.py` |
| 与状态无关的安全规则 | `states/guards.py`（敏感 → 求助 → 抵触 → 结束，责任链按 `order` 执行） |
| 出题与休息话术 | `states/presenter.py`（`RoundPresenter`）、`states/rest_notice.py` |
| 流程结构 | `runtime/workflow.py`（图引擎）+ `runtime/conversation_graph.py`（本项目那张图） |
| 运行态 | `runtime/context.py`（`TurnContext`：会话、当前题、计数、周期计时） |
| 奖励 | `runtime/rewards.py`（`StarRewardPolicy` 策略 + `RewardService`） |
| 落盘记录 | `runtime/recorder.py`（`SessionRecorder`） |
| 家长报告 | `report/*`（聚合、渲染、问答三段分离） |

---

## 三、网页界面（`--web`）

标准库 `ThreadingHTTPServer`，**只监听 127.0.0.1**，静态文件走白名单：

| 页面区域 | 功能 |
| --- | --- |
| 📚 学习 | 对话式答题；选择题渲染成可点按钮；「我不会」按钮走启发式提示而非判错；顶栏实时显示 ⭐/⏱️/✅/🎯 |
| 🌟 打卡 | 今日小目标 + 6 项习惯打卡（可勾可撤）+ 本周习惯报告 |
| 👨‍👩‍👧 家长 | 今日简报 / 本周周报 / 一条建议 / 自由提问 / 题库安全审计 |
| 🔊 朗读 | 浏览器自带语音朗读（自动去掉表情符号），帮识字量有限的孩子 |

接口：`POST /api/start`、`POST /api/say`、`GET /api/status`、`GET /api/habit`、
`POST /api/habit/check`、`POST /api/habit/goal`、`GET /api/parent/{summary,week,advice}`、
`POST /api/parent/ask`、`GET /api/bank`、`GET /api/architecture`。

---

## 四、工作流图（摘要）

```
欢迎页 → 选择科目 → 学习任务 → 答题交互 ⇄ 下一题
            ↘ 习惯打卡 ↗            ↓ 一组 3 题做完
                             奖励反馈 →（再玩一组 / 换科目 / 结束）
任意状态 ──疲劳兜底──▶ 休息提醒 ──休息结束──▶ 回到原位置
任意状态 ──结束兜底──▶ 结束学习 ──「开始」──▶ 欢迎页
```

* 虚线兜底边由 `safety=True` 标记，保证「禁止长时间连续学习」「随时可以结束」无法被绕过；
* 状态机由这张图驱动：**非法流转会抛 `InvalidTransition`**（例如在「休息提醒」里直接出题）；
* 图里加了节点却忘写处理器，启动自检就会报错（`HandlerRegistry.from_graph`）。

---

## 五、四大模块

| 模块 | 内容 | 交互特点 |
| --- | --- | --- |
| 语文启蒙 📖 | 拼音、生字、组词、短句朗读、看图说话、简短古诗 | 带拼音与朗读提示；看图说话只给引导问题，**不给标准答案** |
| 数学启蒙 🔢 | 20 以内加减、数的分与合、认识钟表、人民币、图形、找规律、生活应用题 | 苹果/糖果可视化；引导「数手指、凑十法」；允许多种解法 |
| 英语启蒙 🐣 | 动物/颜色/食物/数字单词、简单短句、儿歌短句 | 听读优先、跟读练习；**不做语法讲解**，长单词会被审计拦下 |
| 学习习惯 🌟 | 课前准备、坐姿、专注、按时收书、整理文具、阅读打卡 | 每天一个小目标；逐项引导；只夸做得好的地方 |

---

## 六、两套对话接口（互相隔离）

```python
from child_teach import ChildTutorAgent

agent = ChildTutorAgent()                 # 数据目录默认 ./data
agent.start()                             # 欢迎页
agent.handle("数学")                       # 【孩子接口】童趣话术 + 状态机
agent.handle("7")
print(agent.parent_summary())              # 【家长接口】简洁客观日报
print(agent.parent_ask("今天正确率多少"))   # 【家长接口】事实问答
agent.architecture()                       # 工作流图 + 处理器绑定（自描述）
```

`handle()` 返回 `TurnResult`：`child_text`（已过红线过滤）、`state`、`state_path`（本轮轨迹）、
`parent_note`（敏感提示 / 结束日报）、`meta`（qid、选项、进度、意图分类）。

### 接入真实大模型（可选）

```python
from child_teach.llm_bridge import LLMBridge

class MyClient:
    def chat(self, messages): ...          # 任何 LLM SDK 包一层即可

bridge = LLMBridge(agent, client=MyClient())
bridge.child_messages("我想学数学")         # 已注入系统提示词 + 运行时状态 + 硬性约束
```

不传 `client` 时自动回退到本地话术引擎，**离线也能完整运行**；模型输出仍会过
`safety.sanitize_child_text`，越界也不会说错话给孩子。

---

## 七、数据持久化（本地 JSON）

| 文件 | 内容 |
| --- | --- |
| `data/profile.json` | 孩子档案、星星、各知识点掌握度与难度、作答记录、需关注清单 |
| `data/learning_history.json` | 每次学习的完整流水（时长、题量、正确率、星星、逐题记录、状态轨迹） |
| `data/habit_log.json` | 每日小目标 + 6 项打卡明细（含时间戳） |

写入为"临时文件 + `os.replace`"原子替换；JSON 损坏时自动备份重建。

两个刻意的设计：
* **一题只记一次**——答错后的提示重试不重复计入题量与正确率；
* **诚实但不打击**——提示后做出来的题标记为 `assisted`，家长报告显示「其中 N 题在提示后完成」。

---

## 八、安全边界（硬编码 + 自动审计）

| 禁止行为 | 实现 |
| --- | --- |
| 超纲题目（100 以上计算、乘除法、复杂语法） | 按知识点的数字上限，命中即**拒绝入库**（`QuestionRepository.add` 抛 `ValueError`） |
| 惩罚性 / 比较式语言 | 全量话术模板审计 + 出口兜底替换（`safety.sanitize_child_text`） |
| 一次输出大量题目 | `AdaptiveEngine.select` 硬截断 3 题 + 单元额度 9 题 |
| 长时间连续学习 | 图的疲劳兜底边 + 周期计时（休息后开新周期） |
| 强迫做题 | 抵触守卫 → 小游戏 / 休息 / 结束，由孩子决定 |
| 敏感话题 | 不展开、不评判，写入 `watchlist` 并在家长简报提示 |

`python main.py --audit` 一键核查；`tests/test_agent.py` 用全流程出口扫描做兜底断言。

---

## 九、自适应难度

* 每个知识点独立维护等级 `1 基础 / 2 巩固 / 3 挑战`，起始为 1；
* 最近 4 次正确率 ≥ 75% 升级、≤ 50% 降级（封顶 3）；
* 作答 ≥ 4 次且正确率 ≥ 80% 标记「已掌握」，选题不再大量重复；回落会自动取消标记；
* 选题权重：错过未对 4.0 ＞ 新题 3.0 ＞ 对过也错过 2.0 ＞ 一直答对 0.6；
  同一知识点每轮最多 2 题，开放题每轮最多 1 题。

---

## 十、扩充题库（三种方式）

```python
from child_teach.domain import Question
from child_teach.repository import QuestionRepository

bank = QuestionRepository()
bank.add(Question(                       # 1) 代码内追加（自动安全审计）
    qid="cn-word-01", subject="chinese", topic="word", difficulty=2,
    kind="choice", stem="「白」的反义词是哪个呀？",
    options=("黑", "红", "蓝"), answer="黑",
    hint="晚上天黑了，和白天相反哦～",
))
bank.load_json("my_questions.json")      # 2) JSON 批量导入
```

题型：`choice` 选择、`fill` 填空（容错中文数字与量词）、`read` 朗读、`speak` 跟读、
`open` 看图说话、`check` 习惯自查。后三种**不判对错**，只记录完成。

新增题目也可以直接编辑 `child_teach/repository/seed_questions.py`（纯数据文件）。

---

## 十一、架构约束由测试固化

`tests/test_architecture.py` 把架构决策变成会失败的规则：

* 单文件 ≤ 240 行、`agent.py` < 200 行（禁止重新长成上帝类）
* 依赖只能单向向下（AST 检查相对导入；`domain` 不得依赖 `infra/repository`）
* 工作流图必须合法、每个节点必须有处理器（缺绑定启动即报错）
* 处理器声明的节点名必须与绑定节点一致、守卫必须按优先级执行

```bash
python -m unittest discover -s tests -v     # 56 个测试
```
