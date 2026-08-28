# OpenAI Messages 风格的真实 Agent 轨迹

> 会话：`full-trajectory-20260828`  
> Agent：`regex`；模型：`ep-20260820165946-646cn`  
> 真实数据：用户消息、Agent 步骤、工具参数、Observation、时间戳均来自运行服务的数据库日志；翻译 SSE 来自本次订阅。  
> 重建边界：项目未落库原始 LLM HTTP 请求体和原始 LLM 文本，因此下文 `messages` 中的 Prompt 和模型回复按固定模板与持久化步骤重建。字段内容、轮次、工具参数、结果和耗时均为真实值；不能将重建文本视为逐字符抓包。

## 如何对应到当前实现

当前 `regex` Agent 不使用 OpenAI 原生 `tool` role。每一轮 LLM 请求实际只有一条 `role = user` 消息，其 `content` 是一段完整 ReAct Prompt；工具 Observation 会拼进下一轮 Prompt 的 `history` 字段。

为了便于按 OpenAI 对话阅读，本文以如下事件形式展示：

```text
user      ：发送给模型的完整任务 Prompt（重建）
assistant ：模型的 Thought / Action（按持久化步骤重建）
tool      ：服务端真实工具调用和真实 Observation
```

`tool` 是阅读上的标准化表示，不是当前代码向 LLM API 发送的原生 message role。

## 共享工具目录

每个子任务的首轮 Prompt 都注入相同的四个工具定义：

```json
[
  {"name": "get_recently_submitted_cs_papers", "purpose": "按天数、CS 子领域和最大数量检索最新论文"},
  {"name": "download_arxiv_pdf", "purpose": "按论文序号、ID 或标题下载 PDF"},
  {"name": "translate_arxiv_pdf", "purpose": "创建异步 PDF 翻译任务"},
  {"name": "get_paper_cache_status", "purpose": "查询原始 PDF 与翻译缓存状态"}
]
```

所有 Prompt 均包含以下约束：每轮只能调用一个工具；Action 必须是严格 JSON；翻译任务创建后直接 `FINISH`；模型可在会话中用 `ref` 引用论文。

---

## 子任务 1：检索论文

真实用户输入时间：`2026-08-28T15:37:42.242801`  
`msg_id`：`969ecfdde4874a63864d9ea5f5969180`

### Round 1：模型决定检索

```json
{
  "messages": [
    {
      "role": "user",
      "content": "你是一个AI研究助手，可以获取最新的arXiv计算机科学论文。\n\n[工具目录：见本文共享工具目录，包含完整参数 Schema]\n\n当前任务：检索最近 1 天 cs.LG 方向的论文，最多 1 篇。\n\n请按 Thought / Action 格式行动；Action 必须为严格 JSON；每次只能调用一个动作。"
    }
  ]
}
```

```json
{
  "role": "assistant",
  "content": "Thought: 用户需要检索最近1天cs.LG方向的论文，最多1篇。我将调用get_recently_submitted_cs_papers工具，设置aspect为'LG'，days为1，max_results为1。\nAction: {\"name\": \"get_recently_submitted_cs_papers\", \"args\": {\"max_results\": 1, \"aspect\": \"LG\", \"days\": 1}}",
  "llm_latency_ms": 7284,
  "recorded_at": "2026-08-28T15:37:54.764413"
}
```

```json
{
  "role": "tool",
  "name": "get_recently_submitted_cs_papers",
  "arguments": {"max_results": 1, "aspect": "LG", "days": 1},
  "tool_latency_ms": 5234,
  "result": {
    "count": 1,
    "paper_id": "2608.27421v1",
    "title": "Learning a Continuous Sepsis Severity Score Without Hour-by-Hour Supervision: A Two-Site Retrospective Study",
    "primary_category": "cs.AI",
    "categories": ["cs.AI", "cs.LG"],
    "pdf_url": "https://arxiv.org/pdf/2608.27421v1"
  },
  "observation": "成功获取 1 篇论文:\n  - Learning a Continuous Sepsis Severity Score Without Hour-by-Hour Supervision: A Two-Site Retrospective Study"
}
```

服务端副作用：将该论文写入 `session_papers`，并设置其 `position = 0`。

### Round 2：模型结束本子任务

```json
{
  "messages": [
    {
      "role": "user",
      "content": "[同一 ReAct Prompt 与工具目录]\n当前任务：检索最近 1 天 cs.LG 方向的论文，最多 1 篇。\n\n历史轨迹：\nThought: 用户需要检索最近1天cs.LG方向的论文，最多1篇。我将调用get_recently_submitted_cs_papers工具，设置aspect为'LG'，days为1，max_results为1。\nAction: {\"name\": \"get_recently_submitted_cs_papers\", \"args\": {\"max_results\": 1, \"aspect\": \"LG\", \"days\": 1}}\nObservation: 成功获取 1 篇论文: Learning a Continuous Sepsis Severity Score Without Hour-by-Hour Supervision: A Two-Site Retrospective Study"
    }
  ]
}
```

```json
{
  "role": "assistant",
  "content": "Action: FINISH",
  "parsed_thought": "未提供思考过程",
  "observation": "任务完成",
  "llm_latency_ms": 2499,
  "tool_latency_ms": 0,
  "recorded_at": "2026-08-28T15:37:57.265737"
}
```

---

## 子任务 2：下载第 1 篇论文

真实用户输入时间：`2026-08-28T15:38:25.517034`  
`msg_id`：`8945437323c441ebbb6f480207eb9e58`

本子任务的 Prompt 实际额外注入了会话上下文：

```text
[会话上下文] 当前会话已有 1 篇论文:
  1. Learning a Continuous Sepsis Severity Score Without Hour-by-Hour Supervision: A Two-Site Retrospective Study
可直接用 ref 序号引用，无需重新搜索。
```

### Round 1：模型决定下载

```json
{
  "messages": [
    {
      "role": "user",
      "content": "[同一 ReAct Prompt 与工具目录]\n当前任务：下载第 1 篇论文的 PDF。\n\n[会话上下文：第 1 篇为 2608.27421v1 对应论文]\n请按 Thought / Action 格式行动。"
    }
  ]
}
```

```json
{
  "role": "assistant",
  "content": "Thought: 当前会话中已有第 1 篇论文，用户要求下载该论文的 PDF，因此直接使用 ref=1 调用下载工具。\nAction: {\"name\": \"download_arxiv_pdf\", \"args\": {\"ref\": 1, \"session_id\": \"full-trajectory-20260828\", \"force\": false}}",
  "llm_latency_ms": 7024,
  "recorded_at": "2026-08-28T15:38:36.103379"
}
```

```json
{
  "role": "tool",
  "name": "download_arxiv_pdf",
  "arguments": {"ref": 1, "session_id": "full-trajectory-20260828", "force": false},
  "tool_latency_ms": 3559,
  "result": {
    "paper_id": "2608.27421v1",
    "status": "READY",
    "existed": false,
    "size_bytes": 1090220,
    "sha256": "ffc0d845c1ee8d5527bf59eec58008e3a769f3fd782b3305608e002fbf38a5d0",
    "local_path": "AgenticArxiv/output/pdf_raw/2608.27421v1.pdf"
  }
}
```

服务端副作用：写入 `pdf_assets`，并把 `sessions.last_active_paper_id` 更新为 `2608.27421v1`。

### Round 2：模型结束本子任务

```json
{
  "messages": [
    {
      "role": "user",
      "content": "[同一 ReAct Prompt 与工具目录]\n当前任务：下载第 1 篇论文的 PDF。\n\n历史轨迹：\nThought: 当前会话中已有第 1 篇论文，用户要求下载该论文的 PDF，因此直接使用 ref=1 调用下载工具。\nAction: {\"name\": \"download_arxiv_pdf\", \"args\": {\"ref\": 1, \"session_id\": \"full-trajectory-20260828\", \"force\": false}}\nObservation: PDF 下载成功，状态 READY，size_bytes 为 1090220。"
    }
  ]
}
```

```json
{
  "role": "assistant",
  "content": "Thought: 第 1 篇论文的 PDF 已成功下载，任务完成。\nAction: FINISH",
  "observation": "任务完成",
  "llm_latency_ms": 4650,
  "tool_latency_ms": 0,
  "recorded_at": "2026-08-28T15:38:40.756049"
}
```

---

## 子任务 3：查询缓存状态

真实用户输入时间：`2026-08-28T15:39:10.554473`  
`msg_id`：`80a1d6e54e904a06ad7cc8704538a7ac`

### Round 1：模型查询缓存

```json
{
  "messages": [
    {
      "role": "user",
      "content": "[同一 ReAct Prompt、工具目录和会话上下文]\n当前任务：查看第 1 篇论文的缓存状态。"
    }
  ]
}
```

```json
{
  "role": "assistant",
  "content": "Thought: 需要查看第1篇论文的缓存状态。\nAction: {\"name\": \"get_paper_cache_status\", \"args\": {\"ref\": 1, \"session_id\": \"full-trajectory-20260828\"}}",
  "llm_latency_ms": 5652,
  "recorded_at": "2026-08-28T15:39:16.223650"
}
```

```json
{
  "role": "tool",
  "name": "get_paper_cache_status",
  "arguments": {"ref": 1, "session_id": "full-trajectory-20260828"},
  "tool_latency_ms": 12,
  "result": {
    "paper_id": "2608.27421v1",
    "pdf_ready": true,
    "translated_ready": false,
    "pdf_status": "READY",
    "translate": null
  }
}
```

### Round 2：模型结束本子任务

```json
{
  "messages": [
    {
      "role": "user",
      "content": "[同一 ReAct Prompt 与工具目录]\n当前任务：查看第 1 篇论文的缓存状态。\n\n历史轨迹：\nThought: 需要查看第1篇论文的缓存状态。\nAction: {\"name\": \"get_paper_cache_status\", \"args\": {\"ref\": 1, \"session_id\": \"full-trajectory-20260828\"}}\nObservation: 原始 PDF 已下载（READY），翻译结果为空。"
    }
  ]
}
```

```json
{
  "role": "assistant",
  "content": "Thought: 任务已完成，第1篇论文的缓存状态为：原始PDF已下载（READY），尚未翻译。\nAction: FINISH",
  "observation": "任务完成",
  "llm_latency_ms": 6984,
  "tool_latency_ms": 0,
  "recorded_at": "2026-08-28T15:39:23.211178"
}
```

---

## 子任务 4：创建异步翻译任务

真实用户输入时间：`2026-08-28T15:39:40.349056`  
`msg_id`：`341a01721f8f4214ae7bb59d57486371`

### Round 1：模型创建任务

```json
{
  "messages": [
    {
      "role": "user",
      "content": "[同一 ReAct Prompt、工具目录和会话上下文]\n当前任务：翻译刚才那篇论文，使用 bing 服务和 4 个线程。\n\n规则：translate_arxiv_pdf 是异步任务；调用后直接 FINISH，不轮询。"
    }
  ]
}
```

```json
{
  "role": "assistant",
  "content": "Thought: 用户要求翻译刚才那篇论文，即会话中的第1篇论文。调用翻译工具，使用 bing 服务和 4 个线程。\nAction: {\"name\": \"translate_arxiv_pdf\", \"args\": {\"ref\": 1, \"session_id\": \"full-trajectory-20260828\", \"force\": false, \"service\": \"bing\", \"threads\": 4, \"keep_dual\": false}}",
  "llm_latency_ms": 8536,
  "recorded_at": "2026-08-28T15:39:48.908154"
}
```

```json
{
  "role": "tool",
  "name": "translate_arxiv_pdf",
  "arguments": {
    "ref": 1,
    "session_id": "full-trajectory-20260828",
    "force": false,
    "service": "bing",
    "threads": 4,
    "keep_dual": false
  },
  "tool_latency_ms": 16,
  "result": {
    "task_id": "06745237fa7f411f9ce5b757ef68e634",
    "paper_id": "2608.27421v1",
    "status": "PENDING"
  },
  "observation": "已创建翻译任务 task_id=06745237fa7f411f9ce5b757ef68e634, paper_id=2608.27421v1，状态=PENDING。"
}
```

真实 SSE 事件（工具调用后）：

```json
[
  {"type": "task_created", "status": "PENDING", "progress": 0.0},
  {"type": "task_started", "status": "RUNNING", "progress": 0.01},
  {"type": "agent_step", "action_name": "translate_arxiv_pdf", "llm_latency_ms": 8536, "tool_latency_ms": 16},
  {"type": "task_progress", "stage": "prepare", "message": "start resolve inputs"}
]
```

### Round 2：模型结束对话，后台任务继续

```json
{
  "messages": [
    {
      "role": "user",
      "content": "[同一 ReAct Prompt 与工具目录]\n当前任务：翻译刚才那篇论文，使用 bing 服务和 4 个线程。\n\n历史轨迹：\nThought: 用户要求翻译刚才那篇论文，即会话中的第1篇论文。调用翻译工具，使用 bing 服务和 4 个线程。\nAction: {\"name\": \"translate_arxiv_pdf\", \"args\": {\"ref\": 1, \"session_id\": \"full-trajectory-20260828\", \"force\": false, \"service\": \"bing\", \"threads\": 4, \"keep_dual\": false}}\nObservation: 已创建翻译任务，状态 PENDING。"
    }
  ]
}
```

```json
{
  "role": "assistant",
  "content": "Thought: 已成功创建翻译任务，状态为PENDING，无需轮询。翻译任务已提交，任务完成。\nAction: FINISH",
  "observation": "任务完成",
  "llm_latency_ms": 5214,
  "tool_latency_ms": 0,
  "recorded_at": "2026-08-28T15:39:54.130401"
}
```

在这次 `/chat` 结束时，真实数据库状态为：

```json
{
  "translate_tasks": {
    "task_id": "06745237fa7f411f9ce5b757ef68e634",
    "status": "RUNNING",
    "progress": 0.0,
    "error": null
  },
  "translate_assets": {
    "paper_id": "2608.27421v1",
    "status": "TRANSLATING",
    "service": "bing",
    "threads": 4,
    "translated_at": null,
    "error": null
  }
}
```

## 全局汇总

```json
{
  "subtasks": 4,
  "llm_rounds": 8,
  "tool_calls": 4,
  "tool_call_sequence": [
    "get_recently_submitted_cs_papers",
    "download_arxiv_pdf",
    "get_paper_cache_status",
    "translate_arxiv_pdf"
  ],
  "total_chat_wall_time_ms": 56716,
  "total_llm_latency_ms": 47843,
  "total_tool_latency_ms": 8821,
  "framework_overhead_ms": 52,
  "token_usage": "unavailable: current online logs and /chat response do not persist or expose tokens"
}
```
