# research_nanobot 用户使用手册（Team + Inbox 版）

## 1. 手册目标

这份手册用于指导你在本地从 0 到 1 跑通 `research_nanobot` 科研多智能体闭环：

1. Planner 生成方案与验收标准
2. Implementer 调度多个 Worker 进行三轮迭代
3. Reviewer 工具化验收并决定通过/打回
4. 输出最终结论与可追溯日志

## 2. 当前主架构与约束

### 2.1 主架构（当前推荐）

- Team + Inbox（无共享黑板）
- 消息总线：`runtime/inbox/*.jsonl`
- 主执行脚本：`nanobot/skills/research-implementer/scripts/run_inbox_cycle.py`

### 2.2 约束

1. 不修改 nanobot 核心运行时（AgentLoop/Runner 等）
2. 仅在 `skills/scripts/tools` 层实现
3. Worker 对外只共享结构化关键信息，不共享完整报告正文
4. 审查必须可追溯（review evidence + runtime trace）

## 3. 目录与关键文件

### 3.1 关键脚本

1. Planner：`nanobot/skills/research-planner/scripts/generate_plan_bundle.py`
2. Implementer（Inbox 主流程）：`nanobot/skills/research-implementer/scripts/run_inbox_cycle.py`
3. Reviewer（Inbox 审查）：`nanobot/skills/research-reviewer/scripts/review_inbox_run.py`
4. Inbox 工具：
   - `nanobot/skills/research-implementer/scripts/inbox_lib.py`
   - `send_message.py`
   - `read_inbox.py`
   - `ack_message.py`
   - `summarize_round_messages.py`
   - `route_review_feedback.py`

### 3.2 示例数据

1. 基础示例：`examples/research-demo/`
2. 完整 E2E 示例：`examples/research-e2e-ai-case/`
3. 高难度对抗示例：`examples/research-hard-safety-case/`

## 4. 环境准备

在仓库根目录执行：

```bash
cd /Users/jakefan/nanobot
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev,ui]
```

验证环境：

```bash
.venv/bin/python --version
.venv/bin/python -m pytest -q tests/agent/test_research_inbox_scripts.py
```

## 5. 输入文件规范

每个 run 至少需要：

1. `plan/candidates.json`
2. `plan/acceptance_spec.json`
3. Worker 将在运行时自动生成每轮工件：
   - `implementation/<candidate_id>/round_<n>/report.md`
   - `implementation/<candidate_id>/round_<n>/metrics.json`
   - `implementation/<candidate_id>/round_<n>/execution_log.json`
   - `implementation/<candidate_id>/round_<n>/notes.md`

可选：若你要复放已有报告，可提供 `--reports-root` 并使用 `--execution-mode replay|auto`。

推荐：3 轮、候选方案数量 3-5。

## 6. 一键运行（CLI，推荐）

```bash
.venv/bin/python nanobot/skills/research-implementer/scripts/run_inbox_cycle.py \
  --run-root .demo_runs_backend \
  --run-id demo_inbox_run_001 \
  --problem "Your hard research problem" \
  --candidate-count 3 \
  --max-rounds 3 \
  --max-review-cycles 2 \
  --execution-mode live \
  --worker-executor codex \
  --candidates-file examples/research-e2e-ai-case/plan/candidates.json \
  --acceptance-file examples/research-e2e-ai-case/plan/acceptance_spec.json \
  --strict-round-artifacts \
  --skip-auto-plan \
  --debug-console
```

参数说明：

1. `--execution-mode`：
   - `live`：默认，真实执行 Worker 实验并生成工件
   - `replay`：强制复放 `--reports-root` 的预置工件
   - `auto`：有可用预置工件则复放，否则转 live
   - 注意：若验收标准要求“main experiment can be reproduced”，建议使用 `live`
2. `--reports-root`：仅在 `replay/auto` 需要
3. `--strict-round-artifacts`：在 replay 模式下要求每轮工件齐全
4. `--skip-auto-plan`：不自动生成 plan，使用你给定的计划文件
5. `--max-review-cycles`：评审打回后的最大重做次数
6. `--worker-executor`：
   - `codex`：Worker 直接调用 `codex exec` 执行任务（推荐）
   - `simulation`：使用内置仿真实验执行器
7. `--require-codex-success`：当 `codex` 执行失败时不允许回退，直接失败（用于强制真实执行）

## 7. 输出工件解读

假设 `run_dir=.demo_runs_backend/demo_inbox_run_001`。

### 7.1 通信层

- `runtime/inbox/*.jsonl`：角色间消息链（可审计）

### 7.2 过程层

- `runtime/round_summaries/round_1.json`
- `runtime/round_summaries/round_2.json`
- `runtime/round_summaries/round_3.json`
- `runtime/experiment_rounds/round_1.json`（每轮实验执行摘要）
- `implementation/<candidate>/round_<n>/execution_log.json`（可复查实验日志）

### 7.3 评审层

- `review/review_feedback.json`
- `review/review_report.md`

### 7.4 交付层

- `deliverables/final_conclusion_inbox.json`
- `deliverables/final_conclusion_inbox.md`
- `deliverables/pipeline_summary_inbox.json`

### 7.5 调试层

- `debug/runtime_trace.jsonl`
- `debug/runtime_trace.md`

## 8. 如何判断 run 成功

至少满足以下条件：

1. `deliverables/pipeline_summary_inbox.json` 中 `approved=true`
2. `final_conclusion_inbox.json` 存在且含 `winner_candidate_id`
3. `review_feedback.json` 中 hard requirements 全部 PASS
4. `runtime_trace.md` 有完整 start -> round1/2/3 -> review -> finish 链路

## 9. Streamlit UI 使用说明

启动：

```bash
source .venv/bin/activate
streamlit run apps/research_team_interactive_ui.py
```

UI 主要用于：

1. 本地分步调试
2. 查看结论与调试日志
3. 查看 Inbox 消息、线程链路与执行证据（`总览/步骤调试 I/O/通信线程`）

说明：

- 当前推荐 UI 已直接调用 `run_inbox_cycle.py` 主流程。
- 若你要做批量自动化回归，优先使用 CLI。

## 10. 常见问题与排错

### 10.1 Worker 实验执行失败

报错示例：
- `worker experiment execution failed`

处理：
1. 查看 `implementation/<candidate>/round_<n>/execution_log.json`
2. 若使用外部 command，检查 command 超时和输出路径
3. 若使用 replay，检查 `--reports-root` 命名是否符合规范

### 10.2 评审未通过

查看：
- `review/review_feedback.json` 的 `must_fix`

处理：
1. 将 `must_fix` 拆成下一轮 Worker 任务
2. 重跑 implementer + reviewer
3. 直到 `approved=true`

### 10.3 Python 版本不兼容

本项目要求：`>=3.11`。
请使用 `.venv/bin/python`，避免系统 Python 3.8。

## 11. 推荐测试流程（最稳）

1. 先跑 `tests/agent/test_research_inbox_scripts.py`
2. 再用 `examples/research-e2e-ai-case` 跑一次 CLI 全流程
3. 然后切换到你的真实研究输入（或高难度示例）
4. 最后检查 `pipeline_summary_inbox.json` 与 `runtime_trace.md`

## 12. 文档入口

建议按顺序阅读：

1. `README.md`
2. `EASY_START_GUIDE.md`
3. `docs/RESEARCH_MULTI_AGENT_SYSTEM_DESIGN_ZH.md`
4. `docs/RESEARCH_AGENT_TEAM_INBOX_PROTOCOL_ZH.md`
5. `docs/DOCUMENTATION_INDEX_ZH.md`
