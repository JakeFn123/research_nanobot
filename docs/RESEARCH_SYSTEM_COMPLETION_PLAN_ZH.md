# 系统补全计划与执行记录（阶段性完成）

## 说明

本文件用于记录项目从“共享黑板方案”过渡到“Team + Inbox 方案”的阶段性里程碑。

当前推荐架构以以下文档为准：

1. `docs/RESEARCH_MULTI_AGENT_SYSTEM_DESIGN_ZH.md`
2. `docs/RESEARCH_AGENT_TEAM_INBOX_PROTOCOL_ZH.md`
3. `docs/RESEARCH_NANOBOT_USER_MANUAL_ZH.md`

## 阶段 A：共享黑板流程（历史）

历史已完成项（用于回溯）：

1. `run_full_cycle.py` 串并行编排基础能力
2. `worker_board.json / agenda.json` 的结构化协作
3. `review_run.py` 基础评审能力
4. 对应测试与文档初版

> 备注：该阶段文档仍保留用于兼容和迁移，不再作为主路线。

## 阶段 B：Team + Inbox 流程（当前主路线）

已完成项：

1. Inbox 通信基础设施
   - `inbox_lib.py`
   - `send_message.py`
   - `read_inbox.py`
   - `ack_message.py`
2. Inbox 主编排
   - `run_inbox_cycle.py`
3. Reviewer Inbox 审核
   - `review_inbox_run.py`
4. 轮次消息聚合与打回路由
   - `summarize_round_messages.py`
   - `route_review_feedback.py`
5. Inbox 测试
   - `tests/agent/test_research_inbox_scripts.py`

## 阶段 C：文档统一（当前进行中）

目标：统一中文文档口径，避免“共享黑板主流程”与“Inbox 主流程”冲突。

已完成：

1. 新增文档总览：`docs/DOCUMENTATION_INDEX_ZH.md`
2. 更新 README 中文项目介绍与导航
3. 更新用户手册为 Team + Inbox 主流程
4. 更新 Streamlit 指南，明确 UI 与主流程关系

## 当前验收口径

以 Team + Inbox 路径为主：

1. 可通过 `run_inbox_cycle.py` 完成 3 轮闭环
2. 输出 `runtime/inbox/*.jsonl`、`review_feedback.json`、`final_conclusion_inbox.json`、`runtime_trace.*`
3. Reviewer 可给出可追溯 evidence 并支持打回重做
