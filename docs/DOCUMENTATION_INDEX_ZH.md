# research_nanobot 文档总览（中文）

本页是 `research_nanobot` 的统一文档入口，优先阅读顺序如下。

## 1. 首次使用（必读）

1. [README.md](../README.md)
   - 项目简介（中文）
   - 快速开始
   - 关键能力与入口
2. [EASY_START_GUIDE.md](../EASY_START_GUIDE.md)
   - 10 分钟内跑通基础能力
3. [RESEARCH_NANOBOT_USER_MANUAL_ZH.md](./RESEARCH_NANOBOT_USER_MANUAL_ZH.md)
   - 完整用户手册（从 0 到 1 跑通科研流程）

## 2. 系统设计（Team + Inbox）

1. [RESEARCH_MULTI_AGENT_SYSTEM_DESIGN_ZH.md](./RESEARCH_MULTI_AGENT_SYSTEM_DESIGN_ZH.md)
   - 总体架构与闭环流程
2. [RESEARCH_AGENT_TEAM_INBOX_PROTOCOL_ZH.md](./RESEARCH_AGENT_TEAM_INBOX_PROTOCOL_ZH.md)
   - Agent 间消息协议（JSONL Inbox）

## 3. UI 与工程化

1. [STREAMLIT_UI_GUIDE_ZH.md](./STREAMLIT_UI_GUIDE_ZH.md)
   - 本地 Streamlit 可视化测试台（含新交互式 Agent Team UI）
2. [OPENSPEC_PROJECT_PLAYBOOK.md](./OPENSPEC_PROJECT_PLAYBOOK.md)
   - OpenSpec 变更管理与校验

## 4. 维护/历史文档

1. [RESEARCH_SYSTEM_COMPLETION_PLAN_ZH.md](./RESEARCH_SYSTEM_COMPLETION_PLAN_ZH.md)
   - 历史阶段的落地计划与里程碑（用于回溯，不作为当前唯一实现规范）

## 5. 当前推荐执行路径（简版）

1. 准备 `plan/candidates.json` 与 `plan/acceptance_spec.json`
2. 准备每个候选方案 3 轮报告与指标
3. 运行 `run_inbox_cycle.py`（Team+Inbox 主流程）
4. 查看 `deliverables/final_conclusion_inbox.json` 与 `debug/runtime_trace.md`
5. 若评审未通过，按 `review/review_feedback.json` 打回重做

## 6. 文档一致性说明

为避免冲突，当前仓库以 **Team + Inbox（无共享黑板）** 作为主架构；
若文档中出现旧版 `worker_board.json` / `run_full_cycle.py` 描述，请以本页链接的“系统设计”和“用户手册”最新内容为准。
