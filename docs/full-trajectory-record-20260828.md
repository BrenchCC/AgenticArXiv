# AgenticArxiv 真实全流程轨迹记录

> 记录时间：2026-08-28 15:37—15:39（Asia/Shanghai）
> 数据来源：已启动的本地服务、`/chat` 实际响应、SSE 事件流、`chat_logs` 与 `agent_steps` 持久化日志。
> 会话：`full-trajectory-20260828`
> Agent：`regex`；模型：`ep-20260820165946-646cn`

本文不是流程示例，而是一次真实服务调用的完整记录。四个已注册工具均通过 Agent 的 `/chat` 调用：检索、下载、缓存查询和创建异步翻译任务。

## 运行范围与可验证性

- 共执行 4 次 `/chat`，产生 8 条 Agent 步骤：每次均为 1 次工具调用 + 1 次 `FINISH`。
- 所有工具调用正常结束；翻译工具的职责是创建后台任务，而非同步等待翻译完成。
- 翻译任务 `06745237fa7f411f9ce5b757ef68e634` 在本文记录结束时仍为 `RUNNING`，进度为 `0.0`；不将其表述为已翻译完成。
- 当前项目未持久化实际完整 Prompt 或 Token 到数据库，`/chat` 也不返回二者。因此本文给出真实用户输入、真实 Thought/Action/Observation 和基于源码模板重建的 Prompt 结构；Token 标为“未暴露”，不伪造数值。

## 任务总览


| 轮次 | 用户输入                                      | 实际工具                           | `msg_id`                           |  对话耗时 | LLM 累计耗时 | 工具累计耗时 |
| ------ | ----------------------------------------------- | ------------------------------------ | ------------------------------------ | ----------: | -------------: | -------------: |
| 1    | 检索最近 1 天 cs.LG 方向的论文，最多 1 篇。   | `get_recently_submitted_cs_papers` | `969ecfdde4874a63864d9ea5f5969180` | 15,027 ms |     9,783 ms |     5,234 ms |
| 2    | 下载第 1 篇论文的 PDF。                       | `download_arxiv_pdf`               | `8945437323c441ebbb6f480207eb9e58` | 15,242 ms |    11,674 ms |     3,559 ms |
| 3    | 查看第 1 篇论文的缓存状态。                   | `get_paper_cache_status`           | `80a1d6e54e904a06ad7cc8704538a7ac` | 12,661 ms |    12,636 ms |        12 ms |
| 4    | 翻译刚才那篇论文，使用 bing 服务和 4 个线程。 | `translate_arxiv_pdf`              | `341a01721f8f4214ae7bb59d57486371` | 13,786 ms |    13,750 ms |        16 ms |

同步对话总耗时为 **56,716 ms**；其中 LLM 为 **47,843 ms**，工具为 **8,821 ms**，框架开销约 **52 ms**。翻译后台执行时间不包含在第 4 次 `/chat` 的耗时中。

## Prompt 记录口径

当前实现只将用户消息、最终回复和每步轨迹持久化；完整 Prompt 没有落库。因此下列内容是根据本次真实输入、真实会话上下文和固定 Prompt 模板重建的准确结构，而不是从数据库读出的逐字符请求体。

每轮均包含：

```text
你是一个 AI 研究助手，可以获取最新的 arXiv 计算机科学论文。

可用工具：四个工具的名称、描述和 JSON 参数 Schema
当前任务：{本轮真实用户输入 + 已有会话论文标题（若存在）}

输出约束：
- 按 Thought / Action 格式输出
- 每次只能调用一个工具
- Action 必须是严格 JSON
- 指代最近操作的论文时，ref 使用 null
- 翻译任务创建后直接 FINISH，不轮询

历史轨迹：{本次 /chat 内前一轮的 Thought / Action / Observation}
```

从第 2 轮开始，真实会话上下文包含：

```text
[会话上下文] 当前会话已有 1 篇论文:
  1. Learning a Continuous Sepsis Severity Score Without Hour-by-Hour Supervision: A Two-Site Retrospective Study
可直接用 ref 序号引用，无需重新搜索。
```

## 第 1 轮：真实检索轨迹

### 输入

```text
检索最近 1 天 cs.LG 方向的论文，最多 1 篇。
```

### 持久化步骤


| Step | Thought                                                                                                      | Action                                                                              | Observation                                                                                                                     |      LLM |     Tool |
| ------ | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ---------: | ---------: |
| 0    | 用户需要检索最近1天cs.LG方向的论文，最多1篇。我将调用工具，设置 aspect 为`LG`、days 为 1、max_results 为 1。 | `get_recently_submitted_cs_papers`，`{"max_results": 1, "aspect": "LG", "days": 1}` | 成功获取 1 篇论文：Learning a Continuous Sepsis Severity Score Without Hour-by-Hour Supervision: A Two-Site Retrospective Study | 7,284 ms | 5,234 ms |
| 1    | 未提供思考过程                                                                                               | `FINISH`                                                                            | 任务完成                                                                                                                        | 2,499 ms |     0 ms |

### 实际输出与状态变化

- 论文 ID：`2608.27421v1`
- 主分类：`cs.AI`；分类集合：`cs.AI`、`cs.LG`
- arXiv PDF URL：`https://arxiv.org/pdf/2608.27421v1`
- `session_papers`：写入该论文，`position = 0`
- `chat_logs`：写入用户消息和 Agent 回复
- `agent_steps`：写入 2 条步骤记录

## 第 2 轮：真实下载轨迹

### 输入

```text
下载第 1 篇论文的 PDF。
```

### 持久化步骤


| Step | Thought                                                                                   | Action                                                                                       | Observation                                                             |      LLM |     Tool |
| ------ | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ---------: | ---------: |
| 0    | 当前会话中已有第 1 篇论文，用户要求下载该论文的 PDF，因此直接使用`ref = 1` 调用下载工具。 | `download_arxiv_pdf`，`{"ref": 1, "session_id": "full-trajectory-20260828", "force": false}` | 下载成功，`paper_id = 2608.27421v1`，状态 `READY`，此前不存在本地缓存。 | 7,024 ms | 3,559 ms |
| 1    | 第 1 篇论文的 PDF 已成功下载，任务完成。                                                  | `FINISH`                                                                                     | 任务完成                                                                | 4,650 ms |     0 ms |

### 实际输出与状态变化

```text
pdf_url: https://arxiv.org/pdf/2608.27421v1.pdf
local_path: AgenticArxiv/output/pdf_raw/2608.27421v1.pdf
status: READY
existed: false
size_bytes: 1090220
sha256: ffc0d845c1ee8d5527bf59eec58008e3a769f3fd782b3305608e002fbf38a5d0
```

- `pdf_assets`：新增该论文的原始 PDF 资产，下载时间为 `2026-08-28 15:38:36`。
- `sessions.last_active_paper_id`：更新为 `2608.27421v1`。
- 这个状态使“刚才那篇论文”可以被解析为当前论文。

## 第 3 轮：真实缓存查询轨迹

### 输入

```text
查看第 1 篇论文的缓存状态。
```

### 持久化步骤


| Step | Thought                                                                   | Action                                                                           | Observation                                                                        |      LLM |  Tool |
| ------ | --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ---------: | ------: |
| 0    | 需要查看第 1 篇论文的缓存状态。                                           | `get_paper_cache_status`，`{"ref": 1, "session_id": "full-trajectory-20260828"}` | 原始 PDF 为`READY`，翻译资产为空，`pdf_ready = true`，`translated_ready = false`。 | 5,652 ms | 12 ms |
| 1    | 任务已完成，第 1 篇论文的缓存状态为：原始 PDF 已下载（READY），尚未翻译。 | `FINISH`                                                                         | 任务完成                                                                           | 6,984 ms |  0 ms |

### 实际输出

```text
paper_id: 2608.27421v1
pdf_ready: true
translated_ready: false
translate: null
```

这一步验证了下载资产已经可用，同时证明翻译任务在创建前没有历史产物。

## 第 4 轮：真实异步翻译任务轨迹

### 输入

```text
翻译刚才那篇论文，使用 bing 服务和 4 个线程。
```

### 持久化步骤


| Step | Thought                                                                                    | Action                                                                                                                                             | Observation                                                          |      LLM |  Tool |
| ------ | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------: | ------: |
| 0    | 用户要求翻译刚才那篇论文，即会话中的第 1 篇论文。调用翻译工具，使用 bing 服务和 4 个线程。 | `translate_arxiv_pdf`，`{"ref": 1, "session_id": "full-trajectory-20260828", "force": false, "service": "bing", "threads": 4, "keep_dual": false}` | 已创建翻译任务`06745237fa7f411f9ce5b757ef68e634`，状态为 `PENDING`。 | 8,536 ms | 16 ms |
| 1    | 已成功创建翻译任务，状态为 PENDING，无需轮询。翻译任务已提交，任务完成。                   | `FINISH`                                                                                                                                           | 任务完成                                                             | 5,214 ms |  0 ms |

实际模型没有采用 Prompt 中建议的 `ref = null`，而是使用了语义等价的 `ref = 1`；两者都成功定位到同一会话中的论文。这是一次真实观察，而不是预设结果。

### SSE 真实事件记录

服务订阅 `/events?session_id=full-trajectory-20260828` 后，收到以下事件序列：

```text
connected
task_created: task_id = 06745237fa7f411f9ce5b757ef68e634, status = PENDING, progress = 0.0
task_started: status = RUNNING, progress = 0.01
agent_step: translate_arxiv_pdf, llm_latency_ms = 8536, tool_latency_ms = 16
task_progress: stage = prepare, msg = start resolve inputs
agent_step: FINISH, llm_latency_ms = 5214, tool_latency_ms = 0
```

### 文档生成时的真实后台状态

```text
task_id: 06745237fa7f411f9ce5b757ef68e634
status: RUNNING
progress: 0.0
service: bing
threads: 4
translate_assets.status: TRANSLATING
output_mono_path: AgenticArxiv/output/pdf_translated/2608.27421v1-mono.pdf
error: null
```

这正好体现了该项目的异步边界：对话请求在创建任务后已成功结束，而翻译工作继续在后台运行。最终完成或失败事件需要由前端持续订阅 SSE，或通过 `/translate/tasks/{task_id}` 查询。

## 轨迹与数据库对应关系


| 真实行为                        | 数据落点                                                                  |
| --------------------------------- | --------------------------------------------------------------------------- |
| 4 条用户输入与 4 条 Agent 回复  | `chat_logs`，共 8 条记录                                                  |
| 每轮 Tool + FINISH              | `agent_steps`，共 8 条记录                                                |
| 检索出的论文及其“第 1 篇”位置 | `session_papers`，`position = 0`                                          |
| “刚才那篇”的指代              | `sessions.last_active_paper_id = 2608.27421v1`                            |
| 原始 PDF 与校验信息             | `pdf_assets`，状态 `READY`                                                |
| 翻译执行生命周期                | `translate_tasks`，状态 `RUNNING`；`translate_assets`，状态 `TRANSLATING` |

## Token 与可观测性结论

本次真实调用的 Token：**未暴露，不能统计**。

原因是 Agent 运行时会累计 `prompt_tokens`、`completion_tokens` 和 `total_tokens`，但当前实现没有将它们写入 `chat_logs` 或 `agent_steps`，也没有通过 `/chat` 返回。相对地，LLM 与工具耗时已逐步持久化，因此本次能给出精确的时间分解。

建议后续在消息级记录总 Token、总耗时和终止类型，在步骤级记录单轮 Token。这样同一份线上轨迹即可同时回答“做了什么、为什么做、用了多久、消耗多少 Token”。
