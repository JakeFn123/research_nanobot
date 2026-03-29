# 设计与实现一致性复查（2026-03-29）

本文档记录 Team+Inbox 主流程中“设计要求 vs 实际实现”的复查结果与修复状态。

## 1. 结论

本轮已完成核心对齐：

1. Worker 每轮真实执行实验（默认 `execution_mode=live`）。
2. Implementer 不再仅消费预置报告，而是调度 Worker 执行并接收真实产物。
3. Reviewer 增加实验真实性、指标一致性、笔记证据校验。
4. 打回重做时，`must_fix` 会进入下一轮 Worker 执行上下文。

## 2. 复查清单

| 编号 | 设计要求 | 复查前状态 | 修复后状态 | 关键文件 |
|---|---|---|---|---|
| A1 | Worker 按方案实现与实验 | 仅读取预置 `reports_root` | 已新增 Worker 执行器，live 默认生成 report/metrics/log/notes | `research-worker/scripts/execute_worker_experiment.py` |
| A2 | Implementer 并行调度 Worker | 顺序读取报告并 digest | 已并行调度 Worker 执行任务并汇总 | `research-implementer/scripts/run_inbox_cycle.py` |
| A3 | 打回后按 must-fix 重做 | redo 仍主要复用既有工件 | redo 注入 must-fix 到 Worker 执行上下文 | `run_inbox_cycle.py` |
| A4 | 报告准确性需可验证 | reviewer 主要查消息完整性 | reviewer 新增 execution/hash/metric/notes 校验 | `research-reviewer/scripts/review_inbox_run.py` |
| A5 | UI 可见执行证据 | UI 主要看消息/trace | UI 增加 execution_mode 分布和执行证据表 | `apps/research_team_interactive_ui.py` |
| A6 | 文档与实现一致 | 手册默认依赖预置 reports | 手册更新为 live 默认，replay 可选 | `docs/RESEARCH_NANOBOT_USER_MANUAL_ZH.md` |

## 3. 仍需注意

1. `execution_mode=replay` 适合历史复放与对比，不应作为“真实实验准确性”证据来源。
2. 若候选方案配置了外部 command，请确保 command 产物路径与超时配置正确。
3. 若要更强可信度，建议在 acceptance 里启用：
   - `validate_execution_evidence`
   - `verify_report_metric_consistency`
   - `require_worker_notes_evidence`

## 4. 验证建议

1. 运行 `tests/agent/test_research_inbox_scripts.py`。
2. 使用 `--execution-mode live` 跑一轮真实案例。
3. 在 UI 查看 `worker_round_update.payload.execution_mode` 与 `execution_log_ref` 覆盖率。
4. 在 `review_feedback.json` 确认真实性相关条目为 `PASS`。
