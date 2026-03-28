# 基于 nanobot 的科研全流程多智能体系统设计文档

## 1. 文档目标

本文档给出一套可以落地到当前 `nanobot` 架构上的多智能体系统设计方案，用于支持“科研想法的提出、方案规划、实现、实验、总结、评审、迭代、收敛”的完整闭环。

目标系统需要满足以下要求：

1. 采用“规划者 - 实现者 - 评审者”三类主角色闭环。
2. 规划者先将模糊研究需求拆解为可执行方案与验收标准。
3. 实现者针对 3 到 5 个候选方案并行调起等数量的智能体完成实现与实验。
4. 实现者内部必须进行 3 轮“报告 - 讨论 - 迭代 - 再实验”。
5. 评审者必须基于工具和验收标准做客观审查，不达标则退回重做。
6. 最终输出不是单次回答，而是一组结构化产物：最优方案、实现代码、实验报告、讨论记录、评审结论、下一轮建议。

本文档不是论文式概念描述，而是偏工程落地的系统设计说明。

## 2. 设计结论摘要

最核心的设计结论有三点：

1. 当前 `nanobot` 已具备多智能体系统的关键积木：
   - 主 Agent 循环
   - 工具调用框架
   - 子代理执行能力
   - 会话持久化
   - 记忆系统
   - Web 搜索 / 抓取 / Shell / 文件工具

2. 但当前 `nanobot` 的 `spawn`/`SubagentManager` 仍是“后台子任务助手”范式，不足以直接承载“多方案并行实现 + 多轮结构化讨论 + 审查回退”的复杂科研编排。

3. 因此应在现有 `AgentRunner + AgentLoop + SessionManager + ToolRegistry` 之上新增一个“研究工作流编排层”，而不是把所有复杂逻辑直接塞进 prompt 或仅依赖现有 `spawn`。

## 3. 与当前 nanobot 架构的映射

### 3.1 当前可复用能力

结合当前仓库实现，以下能力可直接复用：

- `nanobot/agent/loop.py`
  - 提供主 Agent 的消息处理、工具执行、会话保存和 `process_direct()` 入口。
- `nanobot/agent/runner.py`
  - 提供独立于产品层的 Agent 执行循环，非常适合作为“角色型 Agent”的通用运行内核。
- `nanobot/agent/subagent.py`
  - 提供后台子代理执行能力，可作为并行 worker 的起点。
- `nanobot/agent/tools/*`
  - 已具备文件、Shell、Web、消息、Cron 等工具。
- `nanobot/session/manager.py`
  - 提供会话历史持久化。
- `nanobot/agent/memory.py`
  - 提供长期记忆与历史归档。
- `nanobot/config/schema.py`
  - 提供集中配置入口，可扩展出 `research` 配置。

### 3.2 当前直接不足的地方

如果直接拿现在的 `spawn` 来做这个系统，会遇到四个问题：

1. `spawn` 当前默认把子代理结果压缩成“给主 agent 的 1 到 2 句自然语言摘要”，这会丢失科研工作流所需的结构化产物。
2. 子代理没有“显式任务句柄 / 结果对象 / 工件路径 / 评分结果”这些一等公民概念。
3. 现有子代理更像“辅助任务执行器”，而不是“可追踪、可审计、可迭代的角色节点”。
4. 当前没有一个工作流级别的状态机来表示：
   - 方案生成完成
   - 候选实现完成
   - 第几轮讨论
   - 是否通过评审
   - 是否打回重做

因此，正确做法是：

- 保留现有 Agent/Tool 基础层不动。
- 新增“研究编排层”作为领域层。
- 把 Planner / Implementer / Reviewer 设计成角色化 Agent。
- 把候选方案、实验报告、讨论记录、评审结论全部沉淀为结构化文件。

## 4. 系统目标与非目标

### 4.1 系统目标

本系统要解决的是：

- 输入一个模糊科研目标，例如：
  - “设计一种新的 RAG 结构用于多轮医学问答”
  - “验证某个 idea 是否可以提升代码 Agent 的规划能力”
  - “比较三种方法在某 benchmark 上的效果并自动迭代”
- 自动完成：
  - 研究检索
  - 可行性分析
  - 方案生成
  - 验收标准定义
  - 并行实现
  - 实验与报告
  - 多轮讨论改进
  - 评审与回退
  - 收敛出最优可交付方案

### 4.2 非目标

以下内容不属于本设计的直接目标：

- 严格意义上的全局最优解证明
- 无限预算的 AutoML / NAS 式搜索
- 完全无人监督地处理高风险现实世界实验
- 用一个 prompt 替代真实工程编排

这里的“最优解”在工程上应解释为：

- 在给定预算、轮数、工具能力和验收标准下的当前最优可行解

## 5. 角色设计

系统采用“三主角色 + 多工作者”的结构。

### 5.1 Planner 主 Agent

Planner 是入口角色，负责把模糊需求转为可执行研究计划。

职责：

1. 澄清研究目标与边界。
2. 使用 Web 搜索 / 文献抓取 / 仓库阅读做前置调研。
3. 判断问题是否适合自动化多智能体迭代。
4. 产出 3 到 5 个候选方案。
5. 为每个方案定义：
   - 目标
   - 核心假设
   - 实现路线
   - 风险
   - 资源需求
6. 定义统一验收标准与对比指标。
7. 把结果交给 Implementer。

输出物：

- `plan/plan_brief.md`
- `plan/candidates.json`
- `plan/acceptance_spec.json`
- `plan/research_context.md`

### 5.2 Implementer 主 Agent

Implementer 是中枢编排角色，不直接完成所有编码，而是负责：

1. 根据候选方案数量启动等数量的 Worker Agents。
2. 为每个方案分配独立工作目录与实验上下文。
3. 收集每个 Worker 的实现结果与实验报告。
4. 发起 3 轮讨论和改进。
5. 在多方案之间做结论融合、弱点修复、优势迁移。
6. 形成“当前最优方案”和完整实验档案。
7. 把交付物提交给 Reviewer。

Implementer 更像“研究 PM + 技术负责人 + 实验编排器”的组合。

输出物：

- `implementation/candidate_*/`
- `implementation/round_*/discussion.md`
- `implementation/final_solution/`
- `implementation/final_report.md`
- `implementation/final_summary.json`

### 5.3 Worker Agents

每个候选方案对应一个 Worker Agent。

职责：

1. 理解自己负责的方案。
2. 在独立目录中实现代码。
3. 运行实验。
4. 写出结构化实验报告。
5. 参与讨论轮，回应其他方案结论。
6. 基于讨论结论修改实现并再次实验。

每个 Worker 只对一个方案负责，避免职责混乱。

### 5.4 Reviewer 主 Agent

Reviewer 是闭环的质量门禁，不负责“创造方案”，只负责“基于标准验收”。

职责：

1. 读取 Planner 制定的验收标准。
2. 使用工具核查实现与实验结果。
3. 检查复现实验是否可执行。
4. 检查报告是否真实反映代码与结果。
5. 给出结构化 verdict：
   - pass
   - revise
   - reject
6. 若不通过，明确指出退回原因与修复要求。
7. 通过后生成最终验收报告。

输出物：

- `review/review_report.md`
- `review/review_verdict.json`
- `review/failure_items.json`（若未通过）

## 6. 借鉴 ColaCare 的部分

本设计参考了 ColaCare 的两个核心思想，但做了领域迁移：

### 6.1 并行专家分析

ColaCare 中多个 `DoctorAgent` 并行分析，同一问题由多个专业视角分别给出报告。

在本系统中，对应为：

- 多个候选科研方案并行实现
- 每个方案一个 Worker Agent
- 每个 Worker 输出完整实验报告而不是只给答案

### 6.2 汇总者驱动的多轮协作

ColaCare 中由 `LeaderAgent/MetaAgent` 汇总初始意见，再进行多轮协作讨论，并且 `max_round=3`。

在本系统中，对应为：

- Implementer 先收集第一轮候选实现结果
- 然后组织 3 轮讨论
- 每轮讨论都要求：
  - 互相阅读报告
  - 识别强弱项
  - 提出改进
  - 重新实现 / 重新实验
  - 更新报告

### 6.3 结构化落盘

ColaCare 的另一个重要工程习惯是：

- 每个 Agent 的输出、消息、阶段性总结都落盘保存

这点非常适合科研系统，因为科研过程必须可审计、可复盘、可复现。

因此本设计明确要求：

- 每轮讨论与实验必须落盘
- 每个候选方案必须有独立目录
- 所有关键阶段结果必须有 JSON 和 Markdown 双份产物

## 7. 系统总体架构

建议采用如下逻辑分层：

1. 基础运行层
   - `AgentRunner`
   - `ToolRegistry`
   - `LLMProvider`
   - `SessionManager`
   - `MemoryStore`

2. 研究编排层
   - `ResearchWorkflowManager`
   - `PlannerAgent`
   - `ImplementerAgent`
   - `ReviewerAgent`
   - `WorkerAgentHandle`
   - `DiscussionCoordinator`

3. 工件与状态层
   - `ResearchProjectStore`
   - `ResearchStateMachine`
   - `ArtifactIndex`
   - `MetricsRegistry`

4. 产品入口层
   - CLI 命令：`nanobot research run`
   - 可选 channel 命令：`/research ...`

## 8. 端到端流程设计

### 8.1 主流程

```text
用户需求
  -> Planner 调研与拆解
  -> 生成 3~5 个候选方案 + 验收标准
  -> Implementer 为每个方案启动一个 Worker
  -> Worker 并行实现 + 跑实验 + 写初始报告
  -> Implementer 汇总初始结果
  -> 进行第 1 轮讨论与改进
  -> 进行第 2 轮讨论与改进
  -> 进行第 3 轮讨论与改进
  -> Implementer 汇总最优方案和最终报告
  -> Reviewer 基于验收标准用工具核查
  -> 若不通过，返回 Implementer 重做
  -> 若通过，形成最终交付
```

### 8.2 详细阶段

#### 阶段 A：规划

输入：

- 用户科研目标
- 约束条件
- 可用算力 / 时间 / 数据 / 工具

Planner 执行动作：

1. 文献与项目检索。
2. 现有方法可行性分析。
3. 风险与资源预算评估。
4. 方案拆解。
5. 定义验收标准。

输出：

- 3 到 5 个候选方案
- 每个方案的明确实施说明
- 统一评测协议

#### 阶段 B：并行实现

Implementer 为每个候选方案创建独立目录：

```text
research_runs/<run_id>/implementation/candidate_01/
research_runs/<run_id>/implementation/candidate_02/
...
```

每个 Worker 负责：

1. 读取候选方案说明。
2. 创建或修改代码。
3. 运行实验。
4. 记录指标。
5. 输出初始报告。

输出：

- `implementation_notes.md`
- `experiment_config.json`
- `metrics.json`
- `report.md`

#### 阶段 C：三轮讨论和迭代

每轮固定包含 4 个步骤：

1. 互读
   - Worker 读取其他候选方案报告
2. 讨论
   - 给出自己对其他方案优缺点的判断
3. 融合
   - Implementer 汇总讨论并形成 round-level 改进指令
4. 迭代
   - Worker 按新指令修改实现并重跑实验

轮数固定为 3 轮，除非配置允许提前停止。

#### 阶段 D：最优解汇总

Implementer 在三轮结束后完成：

1. 选择最优候选方案，或组合多个方案优点形成融合版。
2. 生成最终实现目录。
3. 生成最终实验报告。
4. 生成“为什么这是当前最优解”的解释。

#### 阶段 E：评审验收

Reviewer 读取：

- `acceptance_spec.json`
- 最终代码
- 最终报告
- 实验数据
- 讨论记录

Reviewer 使用工具完成：

1. 代码结构检查
2. 命令可执行性检查
3. 关键实验复现
4. 指标比对
5. 报告一致性检查
6. 风险与漏洞检查

结果：

- 通过：输出最终验收报告
- 不通过：生成结构化打回清单

## 9. 为什么需要“工作流编排层”

如果让一个大模型直接通过 prompt 承担所有角色，会出现三个典型问题：

1. 上下文污染
   - 规划、实现、评审混在同一个上下文里，会导致角色偏移和自我宽容。
2. 缺少可审计性
   - 无法明确知道哪一轮是谁提出了哪个修改建议。
3. 缺少工程边界
   - 无法稳定地把“候选方案、指标、报告、评审结论”保存成结构化资产。

所以必须把“角色”和“工作流状态”提升为程序中的一等对象。

## 10. 状态机设计

建议引入显式状态机：

```text
CREATED
PLANNING
PLANNED
IMPLEMENTING
DISCUSSING_ROUND_1
DISCUSSING_ROUND_2
DISCUSSING_ROUND_3
SYNTHESIZING
REVIEWING
REVISE_REQUIRED
PASSED
FAILED
```

状态转换规则：

1. `CREATED -> PLANNING`
2. `PLANNING -> PLANNED`
3. `PLANNED -> IMPLEMENTING`
4. `IMPLEMENTING -> DISCUSSING_ROUND_1`
5. `DISCUSSING_ROUND_1 -> DISCUSSING_ROUND_2`
6. `DISCUSSING_ROUND_2 -> DISCUSSING_ROUND_3`
7. `DISCUSSING_ROUND_3 -> SYNTHESIZING`
8. `SYNTHESIZING -> REVIEWING`
9. `REVIEWING -> PASSED`
10. `REVIEWING -> REVISE_REQUIRED`
11. `REVISE_REQUIRED -> IMPLEMENTING`
12. 任意阶段发生不可恢复错误可进入 `FAILED`

## 11. 目录与工件设计

建议在 workspace 下增加独立工作目录：

```text
workspace/
  research_runs/
    <run_id>/
      project_spec.json
      status.json
      logs/
      plan/
        plan_brief.md
        candidates.json
        acceptance_spec.json
        research_context.md
      implementation/
        candidate_01/
          task.json
          code/
          experiments/
          metrics.json
          report.md
          round_1_notes.md
          round_2_notes.md
          round_3_notes.md
        candidate_02/
        candidate_03/
      discussion/
        round_1/
          cross_reviews.json
          coordinator_summary.md
        round_2/
          cross_reviews.json
          coordinator_summary.md
        round_3/
          cross_reviews.json
          coordinator_summary.md
      synthesis/
        final_choice.json
        final_report.md
        final_artifacts.json
      review/
        review_verdict.json
        review_report.md
        failure_items.json
      deliverables/
        best_solution/
        final_summary.md
        final_summary.json
```

## 12. 数据模型设计

### 12.1 ProjectSpec

```json
{
  "runId": "research_20260328_001",
  "title": "Improve agent planning for software tasks",
  "problemStatement": "...",
  "constraints": {
    "timeBudgetMinutes": 180,
    "maxCandidates": 5,
    "maxDiscussionRounds": 3,
    "maxReviewLoops": 3
  },
  "evaluation": {
    "primaryMetric": "pass_rate",
    "secondaryMetrics": ["latency", "cost", "stability"]
  }
}
```

### 12.2 CandidatePlan

```json
{
  "candidateId": "candidate_01",
  "name": "Tool-first hierarchical planner",
  "hypothesis": "...",
  "implementationSpec": "...",
  "expectedBenefits": ["..."],
  "risks": ["..."],
  "requiredArtifacts": ["code", "metrics", "report"]
}
```

### 12.3 AcceptanceSpec

```json
{
  "hardGates": [
    "code runs successfully",
    "required experiment command is reproducible",
    "report contains actual measured metrics",
    "final solution outperforms baseline on primary metric"
  ],
  "softGates": [
    "report explains failure modes",
    "implementation is modular",
    "cost is acceptable"
  ],
  "reviewThreshold": {
    "hardGatePassRate": 1.0,
    "minimumOverallScore": 0.8
  }
}
```

### 12.4 ExperimentReport

```json
{
  "candidateId": "candidate_01",
  "round": 2,
  "summary": "...",
  "implementationChanges": ["..."],
  "commandsRun": ["pytest ...", "python train.py ..."],
  "metrics": {
    "primary": 0.73,
    "secondary": {
      "latency_ms": 420,
      "cost_usd": 1.82
    }
  },
  "failures": ["..."],
  "nextHypothesis": "..."
}
```

### 12.5 ReviewVerdict

```json
{
  "status": "revise",
  "overallScore": 0.67,
  "hardGateResults": [
    {
      "name": "code runs successfully",
      "passed": true,
      "evidence": "..."
    },
    {
      "name": "outperforms baseline",
      "passed": false,
      "evidence": "..."
    }
  ],
  "mustFix": [
    "baseline comparison missing",
    "report metric source not traceable"
  ],
  "optionalImprovements": [
    "add ablation for prompt format"
  ]
}
```

## 13. Agent 提示词契约

建议每个角色都使用固定的“系统提示词模板 + 结构化输出要求”。

### 13.1 Planner Prompt Contract

Planner 必须输出：

1. 问题重述
2. 文献/项目检索摘要
3. 可行性分析
4. 3 到 5 个候选方案
5. 验收标准
6. 预算与风险

禁止 Planner：

- 直接开始实现
- 在没有证据时虚构指标

### 13.2 Worker Prompt Contract

Worker 必须输出：

1. 方案理解
2. 实现步骤
3. 实验命令
4. 结果指标
5. 失败分析
6. 下一轮改进建议

禁止 Worker：

- 跳过实验直接写结论
- 引用未运行的结果为已验证结果

### 13.3 Reviewer Prompt Contract

Reviewer 必须输出：

1. 验收项逐条核查结果
2. 用到的工具证据
3. 阻塞问题
4. 是否通过
5. 打回要求

禁止 Reviewer：

- 只给主观评价而不提供证据
- 在未运行核验工具时声称已通过

## 14. Implementer 的三轮讨论机制

这是系统成败的关键部分。

### 14.1 Round 0：初始并行实现

每个 Worker 输出初始报告。

### 14.2 Round 1：横向互评

目标：

- 找出各方案初版的明显优劣

每个 Worker 需要：

1. 阅读其他候选报告
2. 指出自己可以借鉴的点
3. 指出其他方案的潜在漏洞
4. 提出下一轮改动计划

### 14.3 Round 2：优势迁移

目标：

- 将不同方案中的有效策略迁移到各自实现中

可能动作：

- 把某方案的数据预处理策略迁移过来
- 引入另一个方案更稳定的评估脚本
- 组合两个方案的模块

### 14.4 Round 3：收敛优化

目标：

- 缩小方案差异
- 确定最终最优方案或融合方案

这一轮更偏“收敛”，而不是继续大幅发散探索。

### 14.5 讨论主持者

建议由 Implementer 内部的 `DiscussionCoordinator` 负责：

1. 汇总每轮 cross-review
2. 提取一致结论
3. 识别冲突点
4. 给每个 Worker 下发下一轮行动指令

## 15. Reviewer 的验收方法

Reviewer 不能只是“读报告”，必须使用工具做核查。

建议 Reviewer 的核查流程：

1. `read_file`
   - 检查报告、配置、指标文件是否存在且一致
2. `list_dir`
   - 检查最终交付目录结构是否完整
3. `exec`
   - 复现关键命令
4. `read_file` + `exec`
   - 比对报告中的指标与实际输出
5. `web_fetch` / `web_search`
   - 必要时核查外部 baseline 或 benchmark 定义

Reviewer 的最终结论必须依赖：

- 工具证据
- 明确标准
- 可追溯的文件路径

## 16. 最优解的工程定义

“最优解”在系统中不应被定义为绝对真理，而应被定义为：

- 在当前轮次、预算、约束和验收标准下，
- 所有候选方案及其 3 轮迭代后，
- 通过 Reviewer 验收，
- 并在主指标和关键副指标上最优或综合最优的方案。

建议使用如下决策规则：

1. 先看硬门槛是否全过。
2. 再看主指标。
3. 主指标接近时比较：
   - 稳定性
   - 复现性
   - 成本
   - 复杂度
4. 必要时允许融合方案胜出。

## 17. 对 nanobot 的具体扩展建议

建议新增以下模块。

### 17.1 新目录

```text
nanobot/research/
  __init__.py
  models.py
  orchestrator.py
  state.py
  store.py
  planner.py
  implementer.py
  reviewer.py
  discussion.py
  prompts.py
  evaluator.py
```

### 17.2 建议新增的核心类

#### ResearchWorkflowManager

职责：

- 驱动整个 run 的生命周期
- 管理状态机
- 调用 Planner / Implementer / Reviewer
- 处理 revise loop

#### ResearchProjectStore

职责：

- 负责所有工件落盘
- 保存索引与状态
- 提供按 run 查询能力

#### PlannerAgent

职责：

- 基于 `AgentRunner` 封装规划流程

#### ImplementerAgent

职责：

- 启动 Worker
- 汇总报告
- 组织 3 轮讨论
- 决定最终候选

#### ReviewerAgent

职责：

- 基于验收标准调用工具完成评审

#### DiscussionCoordinator

职责：

- 汇总 cross-review
- 给出下一轮迭代指令

### 17.3 为什么不建议直接改造 `spawn` 即完成全部需求

原因不是 `spawn` 不好，而是职责不同。

`spawn` 更适合：

- 后台长任务
- 辅助性子问题
- 完成后再通知主 Agent

本系统需要的是：

- 可追踪的多角色状态机
- 结构化工件保存
- 多轮协作与审查
- 可回退和可复现

所以建议：

- `spawn` 保留
- 研究系统使用独立 orchestrator
- orchestrator 内部可复用 `AgentRunner`

## 18. 配置设计建议

建议在 `config.json` 中新增：

```json
{
  "research": {
    "enabled": true,
    "plannerModel": "anthropic/claude-opus-4-5",
    "implementerModel": "anthropic/claude-opus-4-5",
    "workerModel": "anthropic/claude-sonnet-4-5",
    "reviewerModel": "anthropic/claude-opus-4-5",
    "candidateCountMin": 3,
    "candidateCountMax": 5,
    "discussionRounds": 3,
    "maxReviewLoops": 3,
    "parallelWorkers": 5,
    "reviewExecEnabled": true,
    "artifactRoot": "~/.nanobot/workspace/research_runs"
  }
}
```

## 19. CLI 入口设计建议

建议新增命令：

```bash
nanobot research run -m "..." 
nanobot research resume <run_id>
nanobot research status <run_id>
nanobot research review <run_id>
nanobot research export <run_id>
```

### 19.1 `nanobot research run`

功能：

- 创建新 run
- 执行 Planner
- 启动 Implementer
- 自动进入 Reviewer

### 19.2 `nanobot research resume`

功能：

- 从某次中断继续

### 19.3 `nanobot research status`

功能：

- 查看当前阶段、轮次、候选方案状态、是否通过评审

## 20. 一次典型运行示例

输入：

```text
设计一个多智能体代码研究系统，用于提升 bug fixing 任务的成功率。
```

系统可能执行：

1. Planner 检索相关工作：
   - self-refine
   - multi-agent debate
   - planner-executor-reviewer
   - code benchmark practices
2. Planner 生成 4 个方案：
   - 层次规划
   - 多路径并行修复
   - 工具驱动检索增强
   - 讨论式 patch 合成
3. Implementer 启动 4 个 Worker：
   - 每个 Worker 在独立目录做实现
4. 每个 Worker 运行 benchmark 并生成报告
5. 进入 3 轮讨论
6. Implementer 选择“讨论式 patch 合成 + 检索增强”的融合方案
7. Reviewer 复现关键 benchmark，发现缺失 baseline 对照
8. 打回
9. Implementer 增补 baseline 实验后重新提交
10. Reviewer 通过，输出最终报告

## 21. 失败处理与鲁棒性设计

### 21.1 Worker 失败

若某个 Worker 失败：

- 标记该候选方案状态为 `failed`
- 仍允许其他候选继续
- 若失败方案过多，可由 Implementer 触发补位候选

### 21.2 工具失败

工具失败时：

- 保存失败命令
- 保存 stderr / stdout 摘要
- 在下一轮讨论中显式纳入“失败原因分析”

### 21.3 Reviewer 无法复现

若 Reviewer 无法复现：

- 默认不通过
- 生成 `mustFix`
- 要求 Implementer 补充脚本、环境说明或修复实验

## 22. 成本与预算控制

为避免系统无限讨论，建议加入预算控制：

1. 最大候选数：5
2. 固定讨论轮数：3
3. 最大 reviewer 回退次数：3
4. 每轮最大工具调用预算
5. 每个 Worker 最大 token 预算

超预算时的策略：

- 优先停止低分候选
- 压缩讨论轮输入
- 降级模型

## 23. 记忆设计

不建议把单个 run 的所有细节都写入长期记忆。

建议分层：

1. 会话级记忆
   - 当前 run 的详细过程
2. 项目级工件
   - `research_runs/<run_id>/...`
3. 长期记忆
   - 只保存通用经验，例如：
     - 哪类方案常失败
     - 哪类 benchmark 命令最稳定
     - 哪些评审规则最有效

## 24. MVP 实施路线

建议分三期做，而不是一次做满。

### Phase 1：最小可用版本

只实现：

1. Planner
2. 3 个候选方案 Worker 并行
3. 固定 3 轮讨论
4. Reviewer 基础验收
5. 工件落盘

此阶段先不做：

- 多 channel 集成
- 长期记忆优化
- 自动预算重分配
- 可视化 dashboard

### Phase 2：增强版

加入：

1. 状态恢复
2. 更强的指标对比
3. 更丰富的评审器
4. 候选方案淘汰机制

### Phase 3：生产版

加入：

1. Web UI / Dashboard
2. 人工插入节点
3. 多 run 对比
4. 自动经验沉淀

## 25. 关键实现建议

### 25.1 角色运行内核

每个角色都建议基于 `AgentRunner` 运行，而不是复制 `AgentLoop` 逻辑。

原因：

- `AgentRunner` 更轻
- 可单次执行
- 易于做角色隔离

### 25.2 工具权限

建议：

- Planner：
  - `web_search`
  - `web_fetch`
  - `read_file`
- Worker：
  - `read_file`
  - `write_file`
  - `edit_file`
  - `list_dir`
  - `exec`
- Reviewer：
  - `read_file`
  - `list_dir`
  - `exec`
  - 必要时 `web_fetch`

### 25.3 独立工作目录

强烈建议每个候选方案使用独立目录，避免多个 Worker 互相覆盖文件。

### 25.4 结构化输出优先

所有角色尽量输出 JSON + Markdown 双版本。

原因：

- JSON 便于程序继续处理
- Markdown 便于人阅读

## 26. 风险与应对

### 风险 1：角色串味

现象：

- 实现者开始替评审放水

应对：

- 强角色 prompt
- 独立上下文
- Reviewer 独立运行

### 风险 2：讨论流于空谈

现象：

- 讨论只有语言，没有实验增量

应对：

- 每轮必须重新提交：
  - 改动说明
  - 新实验结果
  - 与上一轮差异

### 风险 3：报告与真实结果不一致

应对：

- Reviewer 必须复现关键命令
- 指标必须有文件证据

### 风险 4：成本过高

应对：

- 先做 3 候选方案
- 固定 3 轮
- 提前淘汰明显落后方案

## 27. 最终推荐方案

综合当前 `nanobot` 架构与目标需求，推荐的实现路线是：

1. 不推翻现有 `nanobot` Agent 架构。
2. 在其上新增 `research` 领域层。
3. 以 `PlannerAgent + ImplementerAgent + ReviewerAgent` 为主干。
4. 以多个 Worker Agent 承接并行候选实现。
5. 借鉴 ColaCare 的“并行专家 + 汇总者 + 3 轮协作”模式。
6. 用结构化工件和状态机保证可复现、可审计、可回退。

这是目前最符合 `nanobot` 现有实现、改动面可控、且能够真实落地的方案。

## 28. 参考资料

1. nanobot 当前仓库关键模块：
   - `nanobot/agent/loop.py`
   - `nanobot/agent/runner.py`
   - `nanobot/agent/subagent.py`
   - `nanobot/agent/tools/spawn.py`
   - `nanobot/session/manager.py`
2. ColaCare 仓库：
   - https://github.com/PKU-AICare/ColaCare
3. ColaCare 协作入口：
   - https://raw.githubusercontent.com/PKU-AICare/ColaCare/main/collaboration_pipeline.py
4. ColaCare 框架实现：
   - https://raw.githubusercontent.com/PKU-AICare/ColaCare/main/utils/framework.py
5. ColaCare 论文：
   - https://arxiv.org/abs/2410.02551
