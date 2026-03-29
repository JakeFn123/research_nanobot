# SmolLM2-360M 量化案例（基于 research_nanobot 框架）

本案例使用现有 Team+Inbox 闭环框架，针对 `SmolLM2-360M-Instruct` 设计 3 个量化候选方案，目标是：

- 有效参数存储体积明显下降
- perplexity 与基线大致保持一致
- 全流程可复现且可审计（带完整 debug runtime trace）

## 候选方案

1. `candidate_01` `q8_selective`
- 8-bit，按通道量化注意力/MLP 投影层
- 保留 embedding、norm、lm_head 为高精度
- 强调 perplexity 稳定性

1. `candidate_02` `q6_balanced`
- 6-bit，分组量化（group size 随轮次 128 -> 96 -> 64）
- 在压缩率和质量间折中

1. `candidate_03` `q4_aggressive`
- 4-bit，激进压缩
- 追求最大压缩，接受更高质量风险

## 关键实现说明

- 真实实验脚本：`nanobot/skills/research-worker/scripts/run_smollm2_quant_experiment.py`
- Worker 通过 `candidates.json` 中的 `experiment.command` 直接调用该脚本
- 脚本会输出：
  - `report.md`（结构化章节）
  - `metrics.json`（`primary_metric + secondary_metrics`）
- 评审阶段校验：
  - 实验执行证据、哈希一致性
  - payload 与 metrics 一致性
  - notes 的 adopted/rejected/change/result 证据完整性

## 运行命令（完整闭环）

```bash
.venv/bin/python nanobot/skills/research-implementer/scripts/run_inbox_cycle.py \
  --run-root /Users/jakefan/nanobot/.demo_runs_backend \
  --run-id smollm2_quant_demo \
  --problem "Design and validate a quantization plan for SmolLM2-360M that reduces effective model size while keeping perplexity nearly unchanged." \
  --candidate-count 3 \
  --max-rounds 3 \
  --max-review-cycles 2 \
  --execution-mode live \
  --worker-executor codex \
  --skip-auto-plan \
  --candidates-file /Users/jakefan/nanobot/examples/research-smollm2-quant-case/plan/candidates.json \
  --acceptance-file /Users/jakefan/nanobot/examples/research-smollm2-quant-case/plan/acceptance_spec.json \
  --worker-timeout-sec 3600
```

注意：`--run-root` 建议使用绝对路径，避免 worker 子进程在不同 cwd 下解析相对路径导致产物定位错误。

## 主要产物位置

- `deliverables/pipeline_summary_inbox.json`
- `deliverables/final_conclusion_inbox.json`
- `review/review_feedback.json`
- `debug/runtime_trace.json`
- `debug/runtime_trace.jsonl`
- `debug/runtime_trace_health.json`
- `debug/message_threads.json`
