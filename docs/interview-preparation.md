# AgenticArxiv 面试准备

## 一句话介绍

AgenticArxiv 是一个面向 arXiv 论文检索、下载与中文翻译的可观测 Agent 工作台。项目重点不只是调用工具，而是将 ReAct 推理循环、工具调用协议、业务状态和评测指标解耦，支持在统一任务集上比较不同 Agent 实现。

## 技术流程

```text
用户自然语言任务
  → FastAPI /chat 接收请求
  → 根据 agent_type 选择 Agent（regex / MCP / skill_cli）
  → BaseAgent 注入会话上下文（已有论文、最近操作论文）
  → 组装 Prompt（任务 + 工具说明 + 历史轨迹）
  → LLM 决策 Thought + Action
  → 服务端校验并执行工具
  → 生成 Observation
  → 持久化轨迹、耗时，并用 SSE 实时推送
  → FINISH / 报错 / 达到最多 5 轮后结束
  → 前端展示结果、论文资产、翻译任务和历史日志
```

业务主链路：

```text
检索论文 → 选择或引用论文 → 下载 PDF → 异步翻译 → SSE 推送进度 → 查看或下载资产
```

翻译不会阻塞聊天。Agent 创建翻译任务后即可结束当前对话；后台任务继续下载、翻译，并通过 SSE 推送进度和最终状态。

## 三种 Agent 方案

| 方案 | 工具调用方式 | 面试表达 |
| --- | --- | --- |
| `regex` | LLM 输出 JSON，当前进程直接调用工具 | 最轻量，调用链短，但依赖模型稳定遵守格式 |
| `mcp` | 通过 stdio 的 MCP JSON-RPC 调用子进程 | 协议化、工具可发现、隔离更好，但有异步桥接复杂度 |
| `skill_cli` | LLM 依据 Skill 文档生成受限 CLI 命令 | 工具能力文档化，Token 更低；通过白名单和参数数组避免直接执行模型 Shell |

三种模式只替换工具描述、响应解析和调用通道；ReAct 循环、会话状态、翻译、日志和 SSE 都复用同一个 `BaseAgent`。因此 Benchmark 对比的是协议差异，而不是三套不同的业务实现。

## 数据库字段与设计意图

项目当前使用 SQLAlchemy 管理 7 张核心表。数据库并非只保存最终答案，而是覆盖会话记忆、文件资产、异步任务和 Agent 执行轨迹，使一次任务在服务重启后仍能查询和复盘。

```text
sessions ──< session_papers
    │
    ├──< chat_logs ──< agent_steps
    │
    └──< translate_tasks

session_papers.paper_id ──> pdf_assets.paper_id
                         └─> translate_assets.paper_id
```

这里的关系主要通过业务键 `session_id`、`msg_id` 和 `paper_id` 关联；当前 ORM 没有声明数据库级外键。这降低了本地 SQLite 演示的耦合度，但生产环境若需要强一致性和级联清理，可进一步增加外键约束与迁移脚本。

### 1. 会话与短期记忆

| 表 | 核心字段 | 设计意图 |
| --- | --- | --- |
| `sessions` | `session_id`、`last_active_paper_id`、`last_active_at`、`updated_at` | 一个会话一条记录；保存最近操作的论文，支持“刚才那篇”的指代。`session_id` 唯一且有索引。 |
| `session_papers` | `session_id`、`paper_id`、`title`、`authors`、`summary`、`pdf_url`、`categories`、`position`、`created_at` | 保存某次检索的论文快照；`position` 让“第 1 篇”可稳定解析，`(session_id, position)` 有联合索引。`authors`、`categories`、`links` 以 JSON 文本保存。 |

会话论文有 60 分钟 TTL。这样可以避免历史论文长期占用 Prompt，也降低用户后续引用到过期搜索结果的概率。

### 2. PDF 与翻译资产

| 表 | 核心字段 | 设计意图 |
| --- | --- | --- |
| `pdf_assets` | `paper_id`、`pdf_url`、`local_path`、`status`、`size_bytes`、`sha256`、`downloaded_at`、`error` | 每篇论文一份原始 PDF 缓存；`paper_id` 唯一且有索引。`sha256` 用于完整性校验，`error` 保存失败原因。 |
| `translate_assets` | `paper_id`、`input_pdf_path`、`output_mono_path`、`output_dual_path`、`status`、`service`、`threads`、`translated_at`、`error` | 每篇论文一份翻译产物状态；区分单语与双语 PDF，保存翻译服务和线程数，便于复现性能配置。 |

这两张表体现“资产状态”和“任务状态”分离：资产表描述当前可用文件，任务表描述一次后台执行过程。一次翻译失败不会抹去已有的成功资产。

### 3. 异步翻译任务

| 表 | 核心字段 | 设计意图 |
| --- | --- | --- |
| `translate_tasks` | `task_id`、`session_id`、`paper_id`、`status`、`progress`、`input_pdf_url`、`input_pdf_path`、`output_pdf_path`、`meta`、`error`、`created_at`、`updated_at` | 一次翻译请求一条记录。`task_id` 唯一且有索引，`session_id` 有索引，便于按会话查询进度。`progress` 支持 SSE 实时展示，`meta` 用 JSON 文本承载可扩展配置。 |

典型状态流转：`PENDING → RUNNING → COMPLETED`；失败时进入失败状态并写入 `error`。该设计让前端能够先获得 `task_id`，随后独立订阅进度，而不用长时间阻塞 `/chat` 请求。

### 4. 对话与 Agent 轨迹

| 表 | 核心字段 | 设计意图 |
| --- | --- | --- |
| `chat_logs` | `msg_id`、`session_id`、`role`、`content`、`model`、`agent_type`、`created_at` | 保存用户输入和 Agent 最终回复。`msg_id` 唯一且有索引，`session_id` 有索引；可按会话恢复聊天时间线。 |
| `agent_steps` | `msg_id`、`step_index`、`thought`、`action_name`、`action_args`、`observation`、`llm_latency_ms`、`tool_latency_ms`、`created_at` | 保存一次消息内部的逐步 ReAct 轨迹。`action_args` 为 JSON 文本；分开记录 LLM 和工具耗时，方便定位性能瓶颈。 |

`chat_logs` 与 `agent_steps` 通过 `msg_id` 关联：前者回答“用户问了什么、最终答了什么”，后者回答“中间如何决策、调用什么工具、每步花了多久”。

### 5. 当前 Token 字段缺口与建议设计

运行时已计算 `prompt_tokens`、`completion_tokens` 和 `total_tokens`，但它们尚未写入 `chat_logs` 或 `agent_steps`，所以线上日志页只能查看耗时，不能回溯单次真实 Token。

面试中可将此作为明确的迭代方向：在 `chat_logs` 增加任务级 `total_time_ms`、`total_llm_ms`、`total_tool_ms`、`framework_overhead_ms`、`prompt_tokens`、`completion_tokens`、`total_tokens`、`termination_type`；在 `agent_steps` 增加单步 `prompt_tokens`、`completion_tokens`。这样线上会话、SSE 与 Benchmark 的指标口径可以统一。

## Prompt 与轨迹记录

每轮 Prompt 的核心结构如下：

```text
你是 AI 研究助手。
可用工具：检索、下载 PDF、异步翻译、查询缓存。
当前任务：{用户任务 + 会话上下文}
要求：
- 每轮只能调用一个工具
- Action 必须是严格 JSON
- 指代“刚才那篇”时使用 ref = null
- 翻译是异步任务，创建后直接 FINISH，不轮询
历史轨迹：
Thought / Action / Observation
```

一次完整执行建议记录以下字段：

| 阶段 | 记录内容 |
| --- | --- |
| 输入 | `session_id`、用户任务、Agent 类型、模型 |
| Prompt | 实际发送 Prompt、工具描述、上下文摘要 |
| 每一步 | `step_index`、Thought、Action、Action args、Observation |
| 性能 | 单步 LLM 耗时、单步工具耗时、总耗时、框架开销 |
| 成本 | `prompt_tokens`、`completion_tokens`、`total_tokens` |
| 结果 | 工具调用序列、终止原因、成功或失败、任务与资产 ID |

## 真实服务观测样本

测试会话：`interview-trace-20260828`。

- 输入：`检索最近 1 天 cs.LG 方向的论文，最多 1 篇。`
- Agent：`regex`
- 模型：`ep-20260820165946-646cn`
- 结果：成功返回 1 篇论文，并正常 `FINISH`
- 论文：*Learning a Continuous Sepsis Severity Score Without Hour-by-Hour Supervision: A Two-Site Retrospective Study*

真实轨迹：

| Step | Thought / Action | LLM 耗时 | 工具耗时 |
| --- | --- | ---: | ---: |
| 1 | 判断需要检索；调用 `get_recently_submitted_cs_papers(max_results=1, days=1, aspect=LG)` | 9,344 ms | 5,563 ms |
| 2 | 判断任务完成；`FINISH` | 10,374 ms | 0 ms |

汇总：

- 任务端到端耗时：约 25.3 秒
- LLM 累计耗时：19.72 秒
- 工具累计耗时：5.56 秒
- 工具调用准确：是
- 终止状态：正常 `FINISH`
- SSE：实时收到两条 `agent_step` 事件，与数据库日志一致

运行时会累计 Prompt、Completion 和总 Token。不过当前 `/chat` 响应、日志表和前端日志页尚未持久化或展示 Token，因此在线日志无法读取本次真实 Token 值，不能将其误报为 0。Benchmark 可以从 Agent 的运行结果中获取 Token，线上可观测链路仍需要补齐这一字段。

## 后续问答记录模板

```text
任务编号：
用户输入：
Agent 类型 / 模型：
最终输出：
Prompt 摘要：
轨迹：
  Step 1: Thought → Action → Observation
  Step 2: ...
耗时：
  总耗时 / LLM 耗时 / 工具耗时 / 框架开销
Token：
  Prompt / Completion / Total
结果：
  是否完成、终止原因、工具调用序列
复盘：
  成功原因、异常、下一步优化
```

## 面试难点与回答思路

| 难点 | 解决方式 | 面试表达 |
| --- | --- | --- |
| LLM 输出不稳定 | 严格 JSON 约束、解析降级、工具白名单、迭代上限 | 模型负责决策，服务端负责校验和业务不变量。 |
| “第 1 篇”“刚才那篇”如何理解 | 会话保存论文列表和最近活动论文 | 不把完整聊天无限塞入 Prompt，而是维护任务型短期记忆。 |
| 翻译耗时长 | 后台任务 + 状态持久化 + SSE | 把长任务从推理链路拆出去，保证对话可立即返回。 |
| 三种方案如何公平对比 | 共享 Agent 内核、工具和任务集，只替换协议层 | 控制变量，避免比较到不同业务逻辑。 |
| 如何定位慢 | 拆分 LLM、工具、框架三类耗时 | 不只看总时间，而是能归因到模型、工具或协议。 |
| Skill/CLI 是否危险 | 白名单子命令、`shlex` 解析、参数数组执行，不使用 `shell=True` | 模型文本不直接进入 Shell。 |

## 项目亮点

1. 统一 Agent 内核：新增调用协议时，不需要复制会话、日志、异步任务等业务代码。
2. 可观测性：Thought、Action、Observation、SSE、步骤级耗时均可追溯。
3. 异步工程化：PDF 翻译从对话主链路剥离，用户体验不会被长任务拖住。
4. 多协议实验：不是只实现 MCP 和 Skill，而是用统一 Benchmark 横向验证。
5. 安全边界意识：模型生成命令经过白名单和重构后才执行。

## 30 秒面试版本

我做的是一个面向 arXiv 论文检索、下载和翻译的可观测 Agent 平台。核心是把 ReAct 循环、会话状态、异步任务和日志收敛到统一内核，再通过适配器支持进程内、MCP 和 Skill/CLI 三种工具调用方式。系统会记录每一步决策、工具输入输出、LLM 与工具耗时，并通过 SSE 推送翻译进度。我还构建了标准任务集来比较不同协议的完成率、耗时和 Token 成本。
