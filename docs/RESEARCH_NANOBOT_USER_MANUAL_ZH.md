# research_nanobot 用户使用手册（完整版）

## 1. 文档目标

这份手册用于指导你从 0 到 1 使用 `research_nanobot` 完整跑通科研多智能体闭环流程。

本文覆盖：

1. 环境安装与检查
2. 输入文件准备规范
3. Streamlit 可视化全流程测试
4. CLI 一键全流程运行（Planner -> Implementer -> Reviewer -> Conclusion）
5. 结果文件解读
6. 常见报错与定位方法

## 2. 系统能力边界

本项目遵守以下实现约束：

1. 不修改 nanobot 核心运行时
2. 仅通过 `skills + scripts + tools` 实现功能
3. Worker 不互传完整报告，只共享结构化关键信息
4. 协作通过 `worker_board.json` 和 `agenda.json` 动态推进，而非状态机

## 3. 目录与关键文件

核心目录：

- `nanobot/skills/research-planner/scripts/`
- `nanobot/skills/research-implementer/scripts/`
- `nanobot/skills/research-reviewer/scripts/`
- `nanobot/skills/research-blackboard/scripts/`
- `nanobot/skills/research-report-digest/scripts/`
- `apps/research_flow_ui.py`
- `examples/research-demo/`

核心后端脚本：

1. Planner 计划生成
   - `nanobot/skills/research-planner/scripts/generate_plan_bundle.py`
2. Implementer 完整编排
   - `nanobot/skills/research-implementer/scripts/run_full_cycle.py`
3. Reviewer 验收审查
   - `nanobot/skills/research-reviewer/scripts/review_run.py`
4. Conclusion 结论收敛
   - `nanobot/skills/research-blackboard/scripts/finalize_conclusion.py`

## 4. 安装与环境准备

在仓库根目录执行：

```bash
cd /Users/jakefan/nanobot
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[ui]
```

建议先做最小测试：

```bash
pytest tests/agent/test_research_skill_scripts.py
```

预期：`8 passed`（允许出现 `asyncio_mode` warning）。

## 5. 输入文件规范

### 5.1 计划文件

- `plan/candidates.json`
- `plan/acceptance_spec.json`

默认样例：

- `examples/research-demo/plan/candidates.json`
- `examples/research-demo/plan/acceptance_spec.json`

### 5.2 Worker 报告与指标命名规范

每个候选方案每轮需要一对文件：

- 报告：`<candidate_id>_round_<n>_report.md`
- 指标：`<candidate_id>_round_<n>_metrics.json`

默认样例：

- `examples/research-demo/reports/candidate_01_round_1_report.md`
- `examples/research-demo/reports/candidate_01_round_1_metrics.json`
- `examples/research-demo/reports/candidate_02_round_1_report.md`
- `examples/research-demo/reports/candidate_02_round_1_metrics.json`

### 5.3 评审反馈文件（可选）

建议结构：

```json
{
  "approved": false,
  "must_fix": ["..."],
  "optional_improvements": ["..."],
  "evidence": ["..."]
}
```

默认样例：

- `examples/research-demo/review/review_feedback_approved.json`
- `examples/research-demo/review/review_feedback_rejected.json`

## 6. 方式 A：使用 Streamlit 可视化跑完整流程

### 6.1 启动 UI

```bash
cd /Users/jakefan/nanobot
source .venv/bin/activate
streamlit run apps/research_flow_ui.py
```

浏览器打开：`http://localhost:8501`

### 6.2 推荐配置（可直接跑通）

在左侧配置中设置：

1. `Run Root`: `/Users/jakefan/nanobot/.demo_runs_ui`
2. `Run ID`: `ui_full_cycle_001`
3. `Problem`: `Improve research planning quality`
4. `Round`: `1`
5. `Max Rounds`: `3`
6. `Max Review Cycles`: `2`
7. `Candidates File`: `/Users/jakefan/nanobot/examples/research-demo/plan/candidates.json`
8. `Acceptance File`: `/Users/jakefan/nanobot/examples/research-demo/plan/acceptance_spec.json`
9. `Reports Dir`: `/Users/jakefan/nanobot/examples/research-demo/reports`
10. `Feedback Dir`: `/Users/jakefan/nanobot/examples/research-demo/feedback`
11. `Review Feedback JSON (optional)`: 可留空，或填 `.../review_feedback_rejected.json`

### 6.3 执行

在页签 `一键全流程` 点击 `运行完整流程`。

该按钮会调用后端完整编排脚本：

- `nanobot/skills/research-implementer/scripts/run_full_cycle.py`

### 6.4 验收

查看页签：

1. `结果可视化`
   - `worker_board.json` 已生成
   - `agenda.json` 已生成
2. `结论`
   - `final_conclusion.json` 已生成
   - `final_conclusion.md` 已生成

## 7. 方式 B：使用 CLI 一键跑完整闭环（推荐用于自动化）

### 7.1 基于已有计划文件运行

```bash
cd /Users/jakefan/nanobot

python nanobot/skills/research-implementer/scripts/run_full_cycle.py \
  --run-root "$PWD/.demo_runs_backend" \
  --run-id "backend_demo_001" \
  --problem "Improve research planning quality" \
  --reports-root "$PWD/examples/research-demo/reports" \
  --candidates-file "$PWD/examples/research-demo/plan/candidates.json" \
  --acceptance-file "$PWD/examples/research-demo/plan/acceptance_spec.json" \
  --skip-auto-plan
```

### 7.2 无计划文件时自动生成（Planner 自动化）

```bash
cd /Users/jakefan/nanobot

python nanobot/skills/research-implementer/scripts/run_full_cycle.py \
  --run-root "$PWD/.demo_runs_backend" \
  --run-id "backend_demo_auto_plan" \
  --problem "Improve research planning quality under latency constraints" \
  --candidate-count 3 \
  --max-rounds 3 \
  --reports-root "$PWD/examples/research-demo/reports"
```

## 8. 关键输出文件说明

假设 `run_dir=.demo_runs_backend/backend_demo_001`。

### 8.1 协作层工件

- `shared/worker_board.json`
  - Worker 摘要、peer feedback、全局发现
- `shared/agenda.json`
  - 动态下一轮问题与行动

### 8.2 评审层工件

- `review/review_feedback.json`
  - 通过/打回、必须修复项、证据
- `review/review_report.md`
  - 可读审查报告

### 8.3 交付层工件

- `deliverables/final_conclusion.json`
- `deliverables/final_conclusion.md`
- `deliverables/pipeline_summary.json`

## 9. 如何判断这次运行是否成功

最小判定标准：

1. `review/review_feedback.json` 存在
2. `deliverables/final_conclusion.json` 存在
3. `deliverables/final_conclusion.md` 存在
4. `deliverables/pipeline_summary.json` 存在

快速检查命令：

```bash
RUN_DIR="/Users/jakefan/nanobot/.demo_runs_backend/backend_demo_001"
python -m json.tool "$RUN_DIR/review/review_feedback.json"
python -m json.tool "$RUN_DIR/deliverables/final_conclusion.json"
python -m json.tool "$RUN_DIR/deliverables/pipeline_summary.json"
```

## 10. 常见问题与排错

### 10.1 报错：review feedback file does not exist

原因：路径有空格或文件不存在。

处理：

1. 直接从 Finder/终端复制完整路径
2. 确认该文件真实存在
3. 路径中不要混入换行

### 10.2 报错：candidate_xx_round_3_report.md not found

原因：你设置了 `Round=3`，但目录里只有 round1 数据。

处理：

1. 准备 round2/round3 的报告指标
2. 或继续使用 round1 示例数据
3. CLI 下可开启 fallback（默认已开启）

### 10.3 UI 能运行但结果不完整

优先检查：

1. `Reports Dir` 是否包含 candidate 对应文件
2. `candidate_id` 与文件命名是否一致
3. `candidates.json` 数量与报告文件覆盖是否一致

### 10.4 想让 reviewer 必定打回

可以把 `acceptance_spec.json` 写得更严格，或者传入 `review_feedback_rejected.json` 场景并补充 must_fix。

## 11. 推荐工作流（生产实践）

1. 先用 `examples/research-demo` 跑通完整闭环
2. 再替换成你自己的候选方案与报告数据
3. 固定每轮输出命名规范，便于自动化复盘
4. 将 `pipeline_summary.json` 接入你的实验追踪系统

## 12. 关联文档

- 系统设计文档：`docs/RESEARCH_MULTI_AGENT_SYSTEM_DESIGN_ZH.md`
- UI 使用说明：`docs/STREAMLIT_UI_GUIDE_ZH.md`

