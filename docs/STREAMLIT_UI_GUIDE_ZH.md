# Streamlit 本地可视化测试指南（research_nanobot）

本文档说明如何使用两个 UI：

1. `apps/research_team_interactive_ui.py`（推荐，Team+Inbox 主流程可视化）
2. `apps/research_flow_ui.py`（兼容旧流程 + 基础调试）

## 1. 先明确：UI 当前定位

推荐 UI（`research_team_interactive_ui.py`）主要用于：

1. 运行 Team+Inbox 全流程
2. 可视化展示角色协作消息流（Leader/Workers/Reviewer）
3. 查看每一步 Pipeline 输入/输出（`runtime_trace.json`）
4. 浏览 inbox 交互明细与交付结果

说明：

- 当前主架构是 Team+Inbox，推荐 UI 已直接调用 `run_inbox_cycle.py`。
- `research_flow_ui.py` 保留用于兼容与历史流程调试。

## 2. 安装

```bash
cd /Users/jakefan/nanobot
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[ui]
```

## 3. 启动

```bash
streamlit run apps/research_team_interactive_ui.py
```

兼容 UI：

```bash
streamlit run apps/research_flow_ui.py
```

默认地址：`http://localhost:8501`

## 4. 页面说明

推荐 UI 页签：

1. `总览`
2. `交互流程`
3. `步骤调试 I/O`
4. `Inbox 消息`
5. `交付结果`
6. `帮助`

其中：

1. `交互流程`：角色卡片 + Agent Team 消息流图 + 边统计
2. `步骤调试 I/O`：按步骤查看每个 pipeline 事件输入/输出/工件
3. `Inbox 消息`：按角色/类型/轮次过滤并查看具体消息

## 5. 推荐使用方式

### 方式 A：在新 UI 直接跑主流程（推荐）

1. 打开 `research_team_interactive_ui.py`
2. 左侧填写 `Run Root / Run ID / Problem / plan / reports`
3. 点击 `运行 Team+Inbox`
4. 在页签查看：
   - `交互流程`（消息流图）
   - `步骤调试 I/O`（完整步骤日志）
   - `交付结果`

### 方式 B：CLI 跑主流程，UI 看日志

1. 先在终端执行：

```bash
.venv/bin/python nanobot/skills/research-implementer/scripts/run_inbox_cycle.py \
  --run-root .demo_runs_backend \
  --run-id ui_observe_inbox_001 \
  --problem "Your research problem" \
  --candidate-count 3 \
  --max-rounds 3 \
  --max-review-cycles 2 \
  --reports-root examples/research-e2e-ai-case/reports \
  --candidates-file examples/research-e2e-ai-case/plan/candidates.json \
  --acceptance-file examples/research-e2e-ai-case/plan/acceptance_spec.json \
  --strict-round-artifacts \
  --skip-auto-plan
```

2. 打开 UI，将 `Run Root` 和 `Run ID` 指向上述 run。
3. 在 `Inbox 消息` 页签按角色/消息类型/轮次过滤消息。
4. 在 `步骤调试 I/O` 页签查看 `runtime_trace` 结构化事件。

### 方式 C：在兼容 UI 内执行旧流程（可选）

1. 在左侧填写 `Candidates File / Reports Dir / Acceptance File`。
2. 在 `一键全流程` 点击 `运行完整流程`。
3. 用于验证旧版 `run_full_cycle.py` 路径是否可用。

## 6. 输入命名约定

### Team+Inbox 主流程（CLI）

- 报告：`<candidate_id>_round_<n>_report.md`
- 指标：`<candidate_id>_round_<n>_metrics.json`

推荐示例目录：

- `examples/research-e2e-ai-case/reports/`
- `examples/research-hard-safety-case/reports/`

## 7. 验收检查清单

1. `runtime/inbox/*.jsonl` 已生成
2. `debug/runtime_trace.json` 有完整步骤输入/输出
3. `debug/runtime_trace.md` 有可读时间线
4. `review/review_feedback.json` 有 `approved` 与 `evidence`
5. `deliverables/final_conclusion_inbox.json` 已生成

## 8. 常见问题

### 8.1 Inbox 页签显示空

- 确认你跑的是 `run_inbox_cycle.py`
- 确认 `Run Root / Run ID` 指向正确 run

### 8.2 一键全流程与主架构不一致

- 这是兼容性行为：UI 按钮仍走旧流程。
- 主架构验证请用 `research_team_interactive_ui.py` 或 CLI + 新 UI 观察模式。

### 8.3 文件路径报错

- 使用绝对路径最稳
- 确保 `Candidates File`、`Reports Dir` 与 `Acceptance File` 都存在

## 9. 设计参考

新 UI 的交互布局参考了 Agent Team + Inbox 的展示思路（角色常驻、消息驱动、邮箱协作）：

- https://github.com/shareAI-lab/learn-claude-code/blob/main/docs/zh/s09-agent-teams.md
