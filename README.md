# research_nanobot

`research_nanobot` 是一个基于现有 `nanobot` 运行时约束构建的科研多智能体实验仓库。

这个项目的目标不是重写 `nanobot` 内核，而是在 **不修改核心架构和核心代码** 的前提下，只通过现有 `tools + skills + spawn` 机制，搭建一个面向科研想法全流程的动态多智能体协作系统。

## 项目聚焦

这个仓库当前只关注以下内容：

- 基于 `Planner / Implementer / Worker / Reviewer` 的科研角色设计
- Worker 私有报告与公共 JSON 黑板协作协议
- 基于 `worker_board.json` 的关键信息交换
- 基于 `agenda.json` 的动态议程推进
- 不依赖状态机和核心运行时改造的多智能体实验流程

这个仓库当前不再把重点放在上游 `nanobot` 的聊天渠道、社交网络、Docker 部署、通用机器人使用说明等内容。

## 核心设计原则

本项目遵守以下原则：

1. 不修改 `nanobot` 核心运行时。
2. 只通过 `skills`、配套脚本和现有工具落地系统。
3. Worker 之间不直接共享完整报告。
4. Worker 只共享结构化关键摘要。
5. 动态协作通过共享黑板和议程文件推进，而不是状态机。
6. Reviewer 必须基于工具证据审查，不通过就打回。

详细设计文档见：

- [RESEARCH_MULTI_AGENT_SYSTEM_DESIGN_ZH.md](./docs/RESEARCH_MULTI_AGENT_SYSTEM_DESIGN_ZH.md)

## 当前已实现内容

### Skills

当前已经实现 6 个 research 相关 skills：

- `research-planner`
- `research-implementer`
- `research-worker`
- `research-reviewer`
- `research-blackboard`
- `research-report-digest`

### Scripts

当前已经实现以下核心脚本：

- `nanobot/skills/research-blackboard/scripts/init_research_run.py`
- `nanobot/skills/research-blackboard/scripts/validate_board.py`
- `nanobot/skills/research-blackboard/scripts/upsert_worker_entry.py`
- `nanobot/skills/research-blackboard/scripts/add_peer_feedback.py`
- `nanobot/skills/research-blackboard/scripts/synthesize_findings.py`
- `nanobot/skills/research-blackboard/scripts/generate_agenda.py`
- `nanobot/skills/research-report-digest/scripts/digest_report.py`

### Tests

当前已经覆盖一组协议层测试：

- [test_research_skill_scripts.py](./tests/agent/test_research_skill_scripts.py)

测试内容包括：

- 初始化 research run
- 从私有报告提取摘要
- 将 Worker 摘要写入公共黑板
- 写入 peer feedback
- 聚合全局发现
- 生成下一轮动态议程
- 基于 reviewer feedback 继续生成议程

## 仓库中与本项目最相关的目录

```text
docs/
  RESEARCH_MULTI_AGENT_SYSTEM_DESIGN_ZH.md

examples/
  research-demo/
    plan/
    reports/
    feedback/

nanobot/skills/
  research-planner/
  research-implementer/
  research-worker/
  research-reviewer/
  research-blackboard/
  research-report-digest/

tests/agent/
  test_research_skill_scripts.py
```

## 安装

推荐在虚拟环境中安装：

```bash
git clone <your-repo-url>
cd research_nanobot
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

可选：先跑现有测试，确认协议层脚本正常：

```bash
pytest tests/agent/test_research_skill_scripts.py
```

## 从 0 到 1 跑一个 demo run

下面这组命令会完整演示：

1. 初始化一个 research run
2. 使用两份私有 Worker 报告生成摘要
3. 发布到共享黑板
4. 写入双向 peer feedback
5. 聚合全局发现
6. 生成下一轮动态议程

### 第 1 步：进入仓库并准备目录

```bash
cd research_nanobot
RUN_ROOT="$PWD/.demo_runs"
RUN_ID="demo_run_001"
RUN_DIR="$RUN_ROOT/$RUN_ID"
mkdir -p "$RUN_ROOT"
```

说明：

- 以下 demo 默认在仓库根目录执行。
- 由于多个 Worker 都会写同一个 `worker_board.json`，当前示例必须顺序执行，不要并发写入。

### 第 2 步：初始化 run

```bash
python nanobot/skills/research-blackboard/scripts/init_research_run.py \
  --root "$RUN_ROOT" \
  --run-id "$RUN_ID" \
  --problem "Improve research planning quality" \
  --candidates-file "$PWD/examples/research-demo/plan/candidates.json" \
  --acceptance-file "$PWD/examples/research-demo/plan/acceptance_spec.json"
```

这一步会创建：

- `plan/candidates.json`
- `plan/acceptance_spec.json`
- `shared/worker_board.json`
- `shared/agenda.json`
- `implementation/candidate_01/round_1..3/`
- `implementation/candidate_02/round_1..3/`

### 第 3 步：为 candidate_01 生成私有摘要

```bash
python nanobot/skills/research-report-digest/scripts/digest_report.py \
  --report "$PWD/examples/research-demo/reports/candidate_01_round_1_report.md" \
  --metrics "$PWD/examples/research-demo/reports/candidate_01_round_1_metrics.json" \
  --candidate-id candidate_01 \
  --plan-name "Retrieval-first planning" \
  --round 1 \
  --owner worker_01 \
  --output "$RUN_DIR/shared/candidate_01_digest.json"
```

### 第 4 步：为 candidate_02 生成私有摘要

```bash
python nanobot/skills/research-report-digest/scripts/digest_report.py \
  --report "$PWD/examples/research-demo/reports/candidate_02_round_1_report.md" \
  --metrics "$PWD/examples/research-demo/reports/candidate_02_round_1_metrics.json" \
  --candidate-id candidate_02 \
  --plan-name "Ranking-first planning" \
  --round 1 \
  --owner worker_02 \
  --output "$RUN_DIR/shared/candidate_02_digest.json"
```

### 第 5 步：把两个 Worker 摘要写入公共黑板

```bash
python nanobot/skills/research-blackboard/scripts/upsert_worker_entry.py \
  --board "$RUN_DIR/shared/worker_board.json" \
  --candidate-id candidate_01 \
  --entry-file "$RUN_DIR/shared/candidate_01_digest.json"

python nanobot/skills/research-blackboard/scripts/upsert_worker_entry.py \
  --board "$RUN_DIR/shared/worker_board.json" \
  --candidate-id candidate_02 \
  --entry-file "$RUN_DIR/shared/candidate_02_digest.json"
```

### 第 6 步：写入双向 peer feedback

```bash
python nanobot/skills/research-blackboard/scripts/add_peer_feedback.py \
  --board "$RUN_DIR/shared/worker_board.json" \
  --from-candidate candidate_02 \
  --to-candidate candidate_01 \
  --feedback-file "$PWD/examples/research-demo/feedback/candidate_02_on_candidate_01.json"

python nanobot/skills/research-blackboard/scripts/add_peer_feedback.py \
  --board "$RUN_DIR/shared/worker_board.json" \
  --from-candidate candidate_01 \
  --to-candidate candidate_02 \
  --feedback-file "$PWD/examples/research-demo/feedback/candidate_01_on_candidate_02.json"
```

### 第 7 步：校验黑板结构

```bash
python nanobot/skills/research-blackboard/scripts/validate_board.py \
  --board "$RUN_DIR/shared/worker_board.json"
```

如果这一步没有报错，说明当前共享黑板结构合法。

### 第 8 步：聚合全局发现

```bash
python nanobot/skills/research-blackboard/scripts/synthesize_findings.py \
  --board "$RUN_DIR/shared/worker_board.json"
```

这一步会把以下内容写回黑板：

- `dominant_strengths`
- `dominant_failures`
- `candidate_rank_hint`
- `fusion_opportunities`
- `improvement_targets`

### 第 9 步：生成下一轮动态议程

```bash
python nanobot/skills/research-blackboard/scripts/generate_agenda.py \
  --board "$RUN_DIR/shared/worker_board.json" \
  --agenda "$RUN_DIR/shared/agenda.json" \
  --max-rounds 3
```

### 第 10 步：查看结果

查看共享黑板：

```bash
python -m json.tool "$RUN_DIR/shared/worker_board.json" | sed -n '1,220p'
```

查看动态议程：

```bash
python -m json.tool "$RUN_DIR/shared/agenda.json"
```

### 第 11 步：理解这个 demo 证明了什么

这条 demo run 已经验证：

1. 候选方案可以被初始化成标准研究 run 目录。
2. Worker 可以保留私有报告，仅抽取关键摘要到共享黑板。
3. peer feedback 可以通过 JSON 文档写回黑板。
4. 系统可以从群体黑板自动聚合共识。
5. 系统可以自动生成下一轮动态议程。

这正是当前项目的第一阶段目标：先把“协作协议层”跑通。

## 当前限制

当前版本仍然有明确边界：

1. 还没有把 Planner 自动检索和 `candidates.json` 自动生成封装成一键命令。
2. 还没有把 Implementer 批量 `spawn` Worker 的完整自动化写成单命令流程。
3. 还没有把 Reviewer 的完整回退循环封装成一键执行。
4. 当前更多是“协议层 MVP”，不是“全自动研究工厂”。

这意味着：

- 现在已经可以搭建和验证动态多智能体协作协议。
- 下一阶段才是把这些协议进一步封装成可持续运行的工作流。

## 推荐阅读顺序

如果你是第一次进入这个仓库，建议按这个顺序阅读：

1. 本 README
2. [RESEARCH_MULTI_AGENT_SYSTEM_DESIGN_ZH.md](./docs/RESEARCH_MULTI_AGENT_SYSTEM_DESIGN_ZH.md)
3. [nanobot/skills/README.md](./nanobot/skills/README.md)
4. `nanobot/skills/research-*/SKILL.md`
5. [test_research_skill_scripts.py](./tests/agent/test_research_skill_scripts.py)

## 下一步最自然的开发方向

如果继续实现本项目，下一批最值得做的是：

1. 增加 Planner 自动生成 `candidates.json` 的样例流程。
2. 增加 Implementer 的实际 `spawn` 模板。
3. 增加 Reviewer 的标准化 `review_feedback.json` 模板与示例。
4. 把三轮协作进一步封装成半自动命令链。
