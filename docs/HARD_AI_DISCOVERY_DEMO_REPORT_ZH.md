# Hard Case 实战报告（Team + Inbox + Debug + UI）

本文档记录一次高复杂度科研问题在 `research_nanobot` 中的完整闭环运行：规划、并行实现、互评迭代、评审验收、结论输出，以及 Debug 与 UI 可视化验证。

## 1. 任务定义

- 运行时间：2026-03-29
- run_id：`hard_ai_discovery_20260329`
- 问题：在严重分布偏移下，从多组学 + EHR 中发现早期脓毒症因果生物标志物，要求安全、可解释、可复现。
- 架构：`Planner -> Implementer -> Workers(5) -> Reviewer -> (通过/打回)`

## 2. 输入数据与候选方案

输入目录：

- `examples/research-hard-ai-discovery-case/plan/`
- `examples/research-hard-ai-discovery-case/reports/`

候选方案（5 个）：

1. `candidate_01` Counterfactual-RAG Hypothesis Miner
2. `candidate_02` Tool-Driven Program Synthesis Scientist
3. `candidate_03` Debate-Consensus Scientist Ensemble
4. `candidate_04` Bayesian Active Discovery Loop
5. `candidate_05` Neuro-Symbolic Graph Lab

每个候选均提供 3 轮：

1. `candidate_xx_round_n_report.md`
2. `candidate_xx_round_n_metrics.json`

## 3. 运行命令（已执行）

```bash
.venv/bin/python nanobot/skills/research-implementer/scripts/run_inbox_cycle.py \
  --run-root .demo_runs_backend \
  --run-id hard_ai_discovery_20260329 \
  --problem "Discover robust causal biomarkers for early sepsis from multi-omics + EHR under severe domain shift with safety-critical constraints" \
  --candidate-count 5 \
  --max-rounds 3 \
  --max-review-cycles 2 \
  --reports-root examples/research-hard-ai-discovery-case/reports \
  --candidates-file examples/research-hard-ai-discovery-case/plan/candidates.json \
  --acceptance-file examples/research-hard-ai-discovery-case/plan/acceptance_spec.json \
  --strict-round-artifacts \
  --skip-auto-plan
```

## 4. Pipeline 运行结果

### 4.1 总结

- `approved`：`true`
- `review_cycles`：`1`
- `winner_candidate`：`candidate_03`
- 融合策略：`fusion`（`candidate_03` + supporting `candidate_05`, `candidate_04`）

### 4.2 轮次排名演进（Top3）

1. Round 1：`candidate_03 (0.74)` > `candidate_02 (0.71)` > `candidate_05 (0.70)`
2. Round 2：`candidate_03 (0.82)` > `candidate_05 (0.78)` > `candidate_04 (0.77)`
3. Round 3：`candidate_03 (0.88)` > `candidate_05 (0.84)` > `candidate_04 (0.83)`

### 4.3 Inbox 交互规模

各角色收件箱消息量：

1. `implementer.jsonl`: 77
2. `planner.jsonl`: 1
3. `reviewer.jsonl`: 4
4. `worker_01~05.jsonl`: 各 15

关键消息类型统计：

1. `peer_key_insight`: 60
2. `improvement_proposal`: 60
3. `worker_task_assigned`: 15
4. `worker_round_update`: 15
5. `round_synthesis_ready`: 3
6. `review_request`: 1
7. `review_result_approved`: 1
8. `final_package_ready`: 1

### 4.4 Reviewer 验收

- `must_fix`: 空
- 8 项证据全部 PASS：
1. inbox 渠道初始化
2. 全候选 `worker_round_update` 覆盖
3. peer feedback 已合并
4. round synthesis 已生成
5. review 工具证据可用
6. final conclusion 先决条件满足
7. inbox envelope 字段完整
8. candidate coverage 完整

## 5. Debug 追踪结果

- `debug/runtime_trace.json`：结构化事件全量记录
- `debug/runtime_trace.jsonl`：逐行事件流
- `debug/runtime_trace.md`：可读时间线

本次 run：

1. `event_count = 25`
2. 所有事件均含 `details.inputs / details.outputs / details.artifacts`
3. 覆盖节点：pipeline start、plan handoff、每轮 worker update、round synthesis、review、finish

## 6. UI 可视化闭环验证

启动命令：

```bash
streamlit run apps/research_team_interactive_ui.py --server.port 8510
```

UI 查看路径（Run Root=`.demo_runs_backend`, Run ID=`hard_ai_discovery_20260329`）：

1. `总览`：approved、winner、review 输出、final conclusion
2. `交互流程`：角色卡片 + Agent Team 消息流图
3. `步骤调试 I/O`：按事件索引回放每一步输入/输出/工件
4. `Inbox 消息`：按角色/类型/轮次过滤并查看消息明细
5. `交付结果`：`pipeline_summary_inbox.json`、`final_conclusion_inbox.json`、`review_feedback.json`

## 7. 产物路径

- `run 根目录`：`.demo_runs_backend/hard_ai_discovery_20260329`
- `总结`：`.demo_runs_backend/hard_ai_discovery_20260329/deliverables/pipeline_summary_inbox.json`
- `结论`：`.demo_runs_backend/hard_ai_discovery_20260329/deliverables/final_conclusion_inbox.json`
- `评审`：`.demo_runs_backend/hard_ai_discovery_20260329/review/review_feedback.json`
- `Debug JSON`：`.demo_runs_backend/hard_ai_discovery_20260329/debug/runtime_trace.json`
- `Inbox`：`.demo_runs_backend/hard_ai_discovery_20260329/runtime/inbox/*.jsonl`

