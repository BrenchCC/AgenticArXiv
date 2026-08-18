# AgenticArxiv STAR 简历简述

_基于当前代码与 `data/summary.json` 中 210 次 Benchmark 记录整理_

---

## 🎯 推荐简历版本

设计并实现 arXiv 论文检索、下载与异步翻译 Agent 平台；针对多种工具调用架构难以复用和量化比较的问题，抽象统一 `BaseAgent` ReAct 执行循环与工具注册协议，落地进程内调用、MCP JSON-RPC、Skill/CLI 三种可切换实现，并以 MySQL、后台任务和 SSE 完成会话记忆、执行追踪及实时进度推送；构建覆盖 7 类任务的 210 次对比实验，三种模式均达到 100% 任务完成率和工具调用准确率，其中 Skill/CLI 相对 regex 平均耗时降低 42.7%、Token 消耗降低 21.8%。

## 📋 STAR 拆解

| 要素 | 表述 |
| --- | --- |
| Situation | 论文检索、下载和翻译涉及多步工具协作，且不同 Agent 调用协议容易重复业务逻辑、缺少统一评测 |
| Task | 构建可切换、可观测、可量化比较的 Agent 平台，并保证长耗时翻译不阻塞交互 |
| Action | 抽象共享 ReAct 循环和工具 Registry，实现 regex、MCP、Skill/CLI 三种适配器；统一 session 副作用、异步翻译、SSE 与步骤级指标；建立 7 类任务 Benchmark |
| Result | 完成 210 次运行，三种模式均取得 100% 完成率和工具准确率；Skill/CLI 相对 regex 平均耗时降低 42.7%、Token 降低 21.8% |

## ✍️ 两条 Bullet 版本

- 设计 AgenticArxiv 多实现 Agent 架构，以共享 `BaseAgent` ReAct 循环和 `ToolRegistry` 解耦推理控制与工具协议，支持进程内、MCP JSON-RPC、Skill/CLI 三种模式动态切换，并统一会话记忆、异步任务、SSE 和执行日志
- 构建覆盖搜索、下载、翻译、缓存与复合链路的 210 次 Benchmark；三种 Agent 均实现 100% 任务完成率和工具调用准确率，Skill/CLI 相对 regex 平均端到端耗时降低 42.7%、Token 消耗降低 21.8%

## 💬 30 秒面试版本

这个项目的重点不是 arXiv 检索本身，而是我设计了一套可以横向比较工具调用方案的 Agent 内核。我把 ReAct 循环、会话状态、业务副作用和可观测性放进统一的 `BaseAgent`，再用适配器分别实现进程内、MCP 和 Skill/CLI 调用；PDF 翻译通过后台任务和 SSE 与对话解耦。最后我用 7 类任务完成 210 次实验，三种方案都达到 100% 完成率和工具准确率，Skill/CLI 在这组实验里比 regex 平均快 42.7%，Token 少 21.8%。

## ⚠️ 使用口径

- 保留“在该 210 次 Benchmark / 该任务集上”的限定，避免把实验结果表述成普遍规律
- “100% 准确率”应写成“工具调用准确率”，不要扩大为回答内容 100% 正确
- 如果简历空间有限，优先保留架构动作、210 次实验和两个改进比例
- 若面试官追问，主动说明当前完成率基于 `FINISH`，工具准确率基于预期工具顺序子序列匹配
