# 系统补全计划与执行记录（已完成）

## 目标
在不修改 `nanobot` 核心运行时的前提下，使科研多智能体系统完整满足设计文档要求：角色协作、私有/公共信息隔离、三轮动态迭代、结构化同行反馈、工具化评审与闭环交付。

## P0（必须完成）
1. 并行 Worker 编排（spawn 语义）  
状态：已完成  
执行：新增 `research-worker/scripts/run_worker_round.py` 与 `run_peer_feedback.py`，`run_full_cycle.py` 改为并行拉起 Worker 子进程并汇总产物。

2. Reviewer 可复现实验与一致性核查  
状态：已完成  
执行：`review_run.py` 增加 `verify_report_metric_consistency`、`require_worker_notes_evidence`、自定义命令检查能力。

3. 严格轮次工件校验  
状态：已完成  
执行：`run_full_cycle.py` 默认严格模式；仅在显式传入 `--allow-fallback-round-artifacts` 时允许回退。

4. 黑板写入所有权约束  
状态：已完成  
执行：初始化写入 `worker_ownership`；`upsert_worker_entry.py` 与 `add_peer_feedback.py` 增加 owner/actor 校验。

## P1（质量增强）
1. Notes 结构化证据约束  
状态：已完成  
执行：Worker 子进程自动生成标准 `notes.md` 模板；Reviewer 对 notes 结构做必检。

2. 自动化回归测试补齐  
状态：已完成  
执行：新增 owner 冲突、strict 失败、Reviewer 指标/notes 检测等测试用例。

## P2（文档与交付）
1. 设计文档与用户手册同步  
状态：已完成  
执行：更新 `RESEARCH_MULTI_AGENT_SYSTEM_DESIGN_ZH.md` 与 `RESEARCH_NANOBOT_USER_MANUAL_ZH.md`，同步新默认行为与能力边界。

## 验收标准
1. `pytest tests/agent/test_research_skill_scripts.py` 全通过。  
2. `run_full_cycle.py` 能在严格模式下完成三轮闭环（有工件时通过、缺工件时明确失败）。  
3. 输出包含 `worker_board.json`、`agenda.json`、`review_feedback.json`、`final_conclusion.json`、`pipeline_summary.json`、`runtime_trace.*`。  
