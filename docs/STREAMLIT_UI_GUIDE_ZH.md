# Streamlit 本地可视化测试指南（research_nanobot）

本文档说明如何使用 `apps/research_flow_ui.py` 在本地查看与调试科研流程。

## 1. 先明确：UI 当前定位

当前 UI 主要用于：

1. 本地分步调试（兼容旧流程）
2. 查看结论、调试轨迹
3. 查看 Team+Inbox 消息（`Inbox通信` 页签）

说明：

- 当前主架构是 Team+Inbox，主执行建议使用 CLI 的 `run_inbox_cycle.py`。
- UI 的“一键全流程”按钮仍调用旧版 `run_full_cycle.py`（兼容用途）。

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
streamlit run apps/research_flow_ui.py
```

默认地址：`http://localhost:8501`

## 4. 页面说明

UI 包含以下页签：

1. `一键全流程`
2. `分步执行`
3. `结果可视化`
4. `结论`
5. `调试日志`
6. `Inbox通信`
7. `帮助`

## 5. 推荐使用方式

### 方式 A：CLI 跑主流程，UI 看日志（推荐）

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
3. 在 `Inbox通信` 页签按角色/消息类型/轮次过滤消息。
4. 在 `调试日志` 页签查看 `runtime_trace`。

### 方式 B：在 UI 内执行兼容旧流程（可选）

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
2. `debug/runtime_trace.md` 有完整链路
3. `review/review_feedback.json` 有 `approved` 与 `evidence`
4. `deliverables/final_conclusion_inbox.json` 已生成

## 8. 常见问题

### 8.1 Inbox 页签显示空

- 确认你跑的是 `run_inbox_cycle.py`
- 确认 `Run Root / Run ID` 指向正确 run

### 8.2 一键全流程与主架构不一致

- 这是兼容性行为：UI 按钮仍走旧流程。
- 主架构验证请用 CLI + UI 观察模式。

### 8.3 文件路径报错

- 使用绝对路径最稳
- 确保 `Candidates File`、`Reports Dir` 与 `Acceptance File` 都存在
