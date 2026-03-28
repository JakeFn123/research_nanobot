# 基于 nanobot Tools 与 Skills 的科研全流程动态多智能体系统设计文档

## 1. 文档定位

本文档重新定义一套严格受限于当前 `nanobot` 能力边界的科研多智能体系统方案。

本方案必须满足以下硬约束：

1. 不修改 `nanobot` 整体架构。
2. 不修改 `nanobot` 核心代码。
3. 所有功能实现只允许基于现有 `tools` 能力与 `skills` 机制完成。
4. 不采用状态机式实现作为系统核心。
5. Worker Agents 在互相讨论时不能直接交换完整成果与完整报告。
6. Worker Agents 必须把各自方案的关键信息写入一个公共 JSON 文档。
7. 其余 Worker Agents 必须只基于该公共 JSON 文档提取强弱项、提出改进、寻找更优解。
8. 评审者主 Agent 仍需基于验收标准使用工具验收，不通过则打回给实现者重做。

因此，这份文档不是“如何给 nanobot 增加一个新的研究引擎”，而是“如何在不改核心架构的前提下，用现有 `tools + skills + spawn` 搭建一个动态科研多智能体工作流”。

## 2. 核心设计结论

这套系统应当被实现为：

- 一个由主 Agent 驱动的技能化研究协议
- 多个通过现有 `spawn` 工具拉起的 Worker Agents
- 一组约定好的共享 JSON / Markdown 工件
- 一套通过 Skills 固化的角色行为规范

而不应当被实现为：

- 新增一层 Python 编排内核
- 新增状态机驱动框架
- 改造 `AgentLoop`、`AgentRunner`、`SubagentManager`、`SessionManager`
- 改写核心 prompt 构建流程
- 让 Worker 之间互相发送全部报告

一句话总结：

本系统要做的是“协议层设计”，不是“内核层重构”。

## 3. 为什么必须采用 Tools + Skills 协议层实现

当前 `nanobot` 已经具备以下可直接利用的能力：

- `spawn`
  - 可启动后台子代理
- `read_file`
  - 可读取公共文档与私有工件
- `write_file` / `edit_file`
  - 可维护共享 JSON 黑板和各自实验产物
- `list_dir`
  - 可做目录发现
- `exec`
  - 可运行实验、脚本、评测命令
- `web_search` / `web_fetch`
  - 可做研究检索
- `skills`
  - 可为不同角色注入稳定工作协议

因此，最合理的方案是：

1. 不碰核心运行时。
2. 用 Skills 定义 Planner / Implementer / Reviewer / Worker 的行为协议。
3. 用共享工件定义它们的交互协议。
4. 用现有工具完成检索、实现、实验、总结、讨论、审查。

## 4. 系统总体思路

系统采用“三主角色 + 多 Worker + 公共黑板”的结构：

1. Planner 主 Agent
   - 负责调研、拆解、生成 3 到 5 个候选方案与验收标准。
2. Implementer 主 Agent
   - 负责并行拉起与候选方案数量相同的 Worker Agents。
   - 负责汇总公共黑板中的关键信息，驱动三轮讨论与迭代。
3. Reviewer 主 Agent
   - 负责基于验收标准用工具核查结果。
   - 若不通过，则生成打回要求，交还 Implementer。
4. Worker Agents
   - 每个 Worker 只负责一个候选方案。
   - 每轮只把关键信息写入公共 JSON 黑板。
   - 完整报告保存在自己的私有目录，不直接广播给其他 Worker。

系统的核心不是“谁进入哪个状态”，而是“谁向公共黑板写入什么信息、谁从公共黑板读取什么信息、如何基于这些信息迭代”。

## 5. 与 ColaCare 的对应关系

本方案参考 ColaCare 的思路，但只吸收其协作范式，不照搬其医疗场景实现。

对应关系如下：

1. ColaCare 中多个 DoctorAgents 并行分析。
   - 对应本系统中多个 Worker Agents 并行实现多个候选科研方案。
2. ColaCare 中 MetaAgent 汇总并推进多轮讨论。
   - 对应本系统中的 Implementer 主 Agent。
3. ColaCare 强调多轮协作。
   - 对应本系统中的三轮“关键信息共享 - 互评 - 改进 - 再实验”。
4. ColaCare 将协作结果逐步落盘。
   - 对应本系统中的私有报告目录与公共 JSON 黑板并存机制。

但本方案在一个关键点上比 ColaCare 更严格：

- Worker 之间不能交换完整报告，只能交换“结构化关键摘要”。

## 6. 系统中的两类信息空间

这是整个设计最关键的部分。

### 6.1 私有空间

每个 Worker 拥有自己的私有目录，用于保存：

- 完整实现代码
- 完整实验日志
- 完整实验报告
- 失败分析
- 中间分析文档

这些内容默认不直接发给其他 Worker。

### 6.2 公共空间

所有 Worker 共享一个公共 JSON 黑板。

它只保存“可供同行吸收、比较、批判和借鉴的关键信息”，不保存完整报告正文。

也就是说：

- 私有空间负责完整性
- 公共空间负责协作性

## 7. 公共 JSON 黑板机制

建议在工作区中使用如下公共文件：

`research_runs/<run_id>/shared/worker_board.json`

这个文件是整个动态多智能体系统的协作中心。

### 7.1 黑板的目标

黑板必须承担以下职责：

1. 让每个 Worker 公布自己当前方案的最小必要关键信息。
2. 让其他 Worker 快速识别：
   - 哪些点值得借鉴
   - 哪些点存在漏洞
   - 哪些改进最可能带来收益
3. 让 Implementer 看到整个群体协作的实时格局。
4. 让 Reviewer 在最终验收时能追踪演化路径。

### 7.2 黑板不应包含的内容

黑板中不应包含：

- 全量报告正文
- 全部日志
- 完整实验输出
- 大段自由文本推理
- 整个代码实现

黑板必须保持“高密度、可比对、可机器读取、可复用”的结构。

### 7.3 黑板的数据结构建议

建议采用如下结构：

```json
{
  "run_id": "research_20260328_001",
  "problem": "Improve agent planning quality for research tasks",
  "acceptance_spec_path": "plan/acceptance_spec.json",
  "round_index": 1,
  "workers": {
    "candidate_01": {
      "owner": "worker_01",
      "plan_name": "retrieval-first hierarchical planning",
      "round": 1,
      "status": "active",
      "key_hypothesis": "planning improves when external papers are retrieved before decomposition",
      "implementation_delta": [
        "added retrieval step before plan generation",
        "added ranked task decomposition prompt"
      ],
      "core_metrics": {
        "primary_metric": 0.71,
        "secondary_metrics": {
          "latency_ms": 920,
          "cost_usd": 0.84
        }
      },
      "strengths": [
        "strong literature grounding",
        "stable decomposition quality"
      ],
      "weaknesses": [
        "high latency",
        "plan sometimes too conservative"
      ],
      "transferable_insights": [
        "retrieval-first step helps reject weak ideas early",
        "ranking criteria improves candidate filtering"
      ],
      "open_problems": [
        "insufficient exploration diversity"
      ],
      "proposed_next_move": [
        "inject diversity constraint into candidate generator"
      ],
      "private_report_path": "implementation/candidate_01/round_1/report.md"
    }
  },
  "peer_feedback": {
    "candidate_02_on_candidate_01": {
      "observed_strengths": [
        "strong rejection filtering"
      ],
      "observed_weaknesses": [
        "retrieval cost too high"
      ],
      "borrowable_ideas": [
        "use lightweight retrieval only in planning phase"
      ],
      "suggested_improvement": [
        "separate broad retrieval from deep retrieval"
      ]
    }
  },
  "global_findings": {
    "dominant_strengths": [],
    "dominant_failures": [],
    "candidate_rank_hint": [],
    "fusion_opportunities": []
  }
}
```

## 8. Worker 的信息发布协议

每个 Worker 在每轮结束时，必须执行两件事：

1. 写完整私有报告到自己的目录。
2. 抽取“关键协作信息”写入公共黑板。

这意味着 Worker 的工作被拆成两层：

### 8.1 私有输出层

写入：

- `implementation/candidate_xx/round_y/report.md`
- `implementation/candidate_xx/round_y/metrics.json`
- `implementation/candidate_xx/round_y/experiment.log`

### 8.2 公共输出层

只向 `worker_board.json` 更新自己对应的条目。

公共输出只能包含：

- 核心假设
- 本轮关键改动
- 主指标与必要副指标
- 优势
- 劣势
- 可迁移洞见
- 下一步建议
- 私有报告路径

### 8.3 为什么不能直接共享完整报告

因为直接共享完整报告会导致四个问题：

1. 信息过载
   - Worker 很容易被其他方案的全量细节淹没。
2. 协作失焦
   - 讨论从“提炼强弱项”退化成“互相读长文”。
3. 上下文成本过高
   - 大模型处理多个完整报告会造成 token 和注意力浪费。
4. 难以做结构化复用
   - 完整报告不利于程序化识别可迁移结论。

## 9. Worker 之间的讨论机制

Worker 之间的协作必须通过“公共 JSON 黑板”进行，而不是互相发送全文。

### 9.1 讨论原则

每个 Worker 在开始下一轮前：

1. 读取公共黑板中其他 Worker 的关键信息。
2. 不读取其他 Worker 的完整报告正文，除非 Implementer 特批。
3. 从公共黑板中识别：
   - 谁在主指标上更强
   - 谁的风险更低
   - 谁的可迁移洞见更有价值
4. 写出针对别人的结构化反馈。
5. 基于这些反馈改造自己的方案。

### 9.2 讨论不是自由聊天，而是结构化 peer analysis

建议每个 Worker 每轮必须为每个其他 Worker 生成如下结构：

```json
{
  "observed_strengths": [],
  "observed_weaknesses": [],
  "borrowable_ideas": [],
  "suggested_improvement": []
}
```

这能保证讨论具有以下特征：

- 可比对
- 可聚合
- 可进一步被 Implementer 抽象成群体共识

### 9.3 讨论后的执行要求

Worker 不能只“提出建议”而不落地。

每轮讨论后，每个 Worker 必须明确回答：

1. 本轮借鉴了哪些别人的点。
2. 本轮拒绝了哪些建议，以及为什么。
3. 本轮实际改动了哪些实现。
4. 本轮实验结果是否变好。

## 10. 动态多智能体系统，而不是状态机

本方案明确不以状态机作为核心实现。

### 10.1 为什么不采用状态机

状态机的问题在于：

1. 过于刚性
   - 研究过程天然是动态的、会分叉的、会合并的。
2. 不利于临时插入新任务
   - 例如某轮讨论发现需要新对照实验。
3. 不利于表达群体协作中的局部演化
   - 不同 Worker 的节奏可能不完全同步。

### 10.2 动态实现方式

本系统建议采用“黑板 + 议程队列 + 角色技能协议”的动态模式。

系统真正的推进变量不是“当前状态”，而是：

1. 公共黑板里当前有哪些结论。
2. 还有哪些待解决问题。
3. 哪些 Worker 需要被继续迭代。
4. 当前是否已满足验收标准。

### 10.3 建议的动态控制变量

可在共享目录中维护以下文件：

- `shared/worker_board.json`
- `shared/agenda.json`
- `shared/review_feedback.json`
- `shared/final_synthesis.json`

其中：

#### `agenda.json`

负责描述当前还需要处理的任务，而不是系统状态。

示例：

```json
{
  "current_round": 2,
  "active_candidates": [
    "candidate_01",
    "candidate_02",
    "candidate_03"
  ],
  "priority_questions": [
    "can candidate_02 borrow low-cost retrieval from candidate_01?",
    "does candidate_03 need an additional baseline?"
  ],
  "required_actions": [
    {
      "owner": "candidate_02",
      "action": "reduce retrieval latency without harming planning quality"
    },
    {
      "owner": "candidate_03",
      "action": "add baseline comparison and update metrics"
    }
  ]
}
```

也就是说：

- 系统靠“下一步议程”推进
- 而不是靠“状态迁移图”推进

## 11. 三轮讨论与迭代如何动态实现

你的原始要求仍然保留：

- 系统至少进行三轮讨论和迭代

但实现方式不是状态机，而是通过议程迭代。

### 11.1 第 1 轮

目标：

- 发现每个候选方案的初始强弱项

执行：

1. Worker 完成初版实现与实验。
2. Worker 更新公共黑板。
3. 所有 Worker 读取公共黑板并写 peer feedback。
4. Implementer 从黑板中提取群体共识，更新 `agenda.json`。

### 11.2 第 2 轮

目标：

- 借鉴强项，修复明显缺陷

执行：

1. Worker 根据 `agenda.json` 改造各自方案。
2. 重新实验并更新黑板。
3. 其他 Worker 再次基于黑板判断是否真正改善。
4. Implementer 提炼可融合的模式。

### 11.3 第 3 轮

目标：

- 收敛到当前最优解或融合解

执行：

1. Worker 聚焦少数高价值改动。
2. Implementer 提取最强要素组合。
3. 形成最优候选或融合候选。

### 11.4 动态扩展

虽然基础设计要求 3 轮，但实现上应允许：

- 在评审打回后再次启动新的议程轮
- 继续使用同一套黑板机制

也就是说：

- 三轮是默认协作轮
- 不是僵硬的系统状态边界

## 12. 角色设计

### 12.1 Planner 主 Agent

Planner 的职责：

1. 基于用户模糊需求做研究检索。
2. 形成问题重述。
3. 生成 3 到 5 个候选方案。
4. 为每个方案生成：
   - 目标
   - 关键假设
   - 实现方向
   - 关键风险
5. 输出统一验收标准。
6. 初始化共享目录与公共文件。

Planner 主要依赖的现有工具：

- `web_search`
- `web_fetch`
- `read_file`
- `write_file`
- `edit_file`

Planner 输出：

- `plan/plan_brief.md`
- `plan/candidates.json`
- `plan/acceptance_spec.json`
- `shared/worker_board.json`
- `shared/agenda.json`

### 12.2 Implementer 主 Agent

Implementer 的职责：

1. 读取 `candidates.json`。
2. 用现有 `spawn` 工具拉起与候选方案数量相等的 Worker Agents。
3. 要求每个 Worker：
   - 只在自己的目录工作
   - 写完整私有报告
   - 只把关键信息写到黑板
4. 在每一轮之后：
   - 汇总黑板
   - 提炼优势与弱点
   - 写入新的 `agenda.json`
5. 三轮后形成最优候选或融合方案。
6. 将最终结果提交给 Reviewer。

Implementer 主要依赖的现有工具：

- `spawn`
- `read_file`
- `write_file`
- `edit_file`
- `list_dir`
- `exec`

### 12.3 Worker Agent

每个 Worker 只负责一个候选方案。

Worker 的职责：

1. 读取自己负责的候选方案说明。
2. 在私有目录实现代码。
3. 运行实验。
4. 生成完整实验报告。
5. 抽取关键协作信息到公共黑板。
6. 读取其他 Worker 的黑板条目。
7. 生成结构化 peer feedback。
8. 基于 peer feedback 改进自己的方案。

Worker 使用的工具：

- `read_file`
- `write_file`
- `edit_file`
- `list_dir`
- `exec`
- 必要时 `web_search` / `web_fetch`

### 12.4 Reviewer 主 Agent

Reviewer 的职责：

1. 读取验收标准。
2. 读取最终综合结果。
3. 使用工具复核实现与实验。
4. 判断是否达标。
5. 若不达标，生成结构化打回要求。

Reviewer 使用的工具：

- `read_file`
- `list_dir`
- `exec`
- 必要时 `web_fetch`

Reviewer 输出：

- `review/review_report.md`
- `review/review_feedback.json`

## 13. 只基于 Skills 的实现策略

由于不能改核心架构，所以整个系统必须主要由 Skills 实现。

建议新增以下 Skills：

### 13.1 `research-planner`

作用：

- 规范 Planner 如何做检索、可行性分析、方案拆解、验收标准编写。

### 13.2 `research-implementer`

作用：

- 规范 Implementer 如何启动 Worker、如何维护黑板、如何更新议程。

### 13.3 `research-worker`

作用：

- 规范 Worker 如何：
  - 实现方案
  - 写私有报告
  - 提炼关键摘要
  - 阅读公共黑板
  - 写 peer feedback
  - 根据反馈改进

### 13.4 `research-reviewer`

作用：

- 规范 Reviewer 如何基于验收标准用工具审查。

### 13.5 `research-blackboard`

作用：

- 规范公共 JSON 黑板的字段、写入规则、冲突处理规则。

### 13.6 `research-report-digest`

作用：

- 规范如何从完整实验报告中抽取关键协作信息，而不是直接外发全文。

## 14. Skill 目录建议

不修改核心代码的前提下，建议在 workspace 或 skills 目录中增加如下内容：

```text
workspace/
  skills/
    research-planner/
      SKILL.md
    research-implementer/
      SKILL.md
    research-worker/
      SKILL.md
    research-reviewer/
      SKILL.md
    research-blackboard/
      SKILL.md
    research-report-digest/
      SKILL.md
```

如果允许增加 skills 附带脚本，可再加入：

```text
workspace/
  skills/
    research-blackboard/
      SKILL.md
      scripts/
        validate_board.py
        merge_feedback.py
        rank_candidates.py
```

这里的脚本不是核心架构修改，而是技能配套辅助脚本，调用方式仍然通过现有 `exec` 工具完成。

## 15. 黑板写入规则

为了避免多个 Worker 互相覆盖公共 JSON，必须定义严格的写入协议。

### 15.1 每个 Worker 只拥有自己的写入槽位

例如：

- `workers.candidate_01.*` 只允许 `candidate_01` 自己改
- `workers.candidate_02.*` 只允许 `candidate_02` 自己改

### 15.2 peer feedback 单独命名

例如：

- `peer_feedback.candidate_02_on_candidate_01`

这样可以清楚知道：

- 谁评价了谁
- 评价内容是什么

### 15.3 全局发现由 Implementer 汇总

例如：

- `global_findings`
- `fusion_opportunities`
- `candidate_rank_hint`

这些字段只由 Implementer 更新。

### 15.4 黑板冲突处理

若出现写入冲突，建议使用以下协议：

1. Worker 先读最新版本。
2. 只修改自己拥有的字段。
3. 写入前再次校验。
4. 若结构损坏，则运行黑板修复脚本或由 Implementer 修复。

## 16. 目录与工件设计

建议在 workspace 下创建独立运行目录：

```text
research_runs/
  <run_id>/
    plan/
      plan_brief.md
      candidates.json
      acceptance_spec.json
    shared/
      worker_board.json
      agenda.json
      review_feedback.json
      final_synthesis.json
    implementation/
      candidate_01/
        round_1/
          report.md
          metrics.json
          notes.md
        round_2/
          report.md
          metrics.json
          notes.md
        round_3/
          report.md
          metrics.json
          notes.md
      candidate_02/
      candidate_03/
    synthesis/
      best_candidate.json
      fusion_rationale.md
      final_report.md
    review/
      review_report.md
      review_feedback.json
    deliverables/
      final_summary.md
      final_summary.json
```

## 17. 动态议程机制

整个系统不应维护“状态迁移图”，而应维护“下一步要干什么”的议程。

### 17.1 议程的内容

`agenda.json` 中只需要描述：

1. 当前轮次
2. 当前活跃候选
3. 当前优先问题
4. 每个 Worker 下一步的重点动作
5. 是否已达到送审条件

示例：

```json
{
  "round_index": 2,
  "ready_for_review": false,
  "active_candidates": [
    "candidate_01",
    "candidate_02",
    "candidate_03"
  ],
  "priority_questions": [
    "which retrieval pattern gives the best cost-performance ratio?",
    "can candidate_03 absorb candidate_01's filtering strategy?"
  ],
  "worker_actions": {
    "candidate_01": [
      "keep retrieval-first design but lower latency"
    ],
    "candidate_02": [
      "borrow candidate_03's ranking heuristic"
    ],
    "candidate_03": [
      "run extra baseline comparison"
    ]
  }
}
```

### 17.2 议程的好处

相比状态机，议程更适合科研系统，因为：

1. 可以灵活插入临时实验。
2. 可以允许部分 Worker 先走一步。
3. 可以在打回后直接继续下一个议程，而不是重走状态转换。
4. 更符合“问题驱动”的研究实践。

## 18. Planner 的详细工作流

Planner 的标准流程应为：

1. 接收模糊研究目标。
2. 通过 `web_search` 检索论文、项目、benchmark、实现思路。
3. 通过 `web_fetch` 抓取关键页面。
4. 形成可行性分析。
5. 决定 3 到 5 个候选方案。
6. 为每个方案生成：
   - 方案标题
   - 核心假设
   - 实现重点
   - 预期优势
   - 主要风险
7. 写出 `acceptance_spec.json`。
8. 初始化黑板和议程。

## 19. Implementer 的详细工作流

Implementer 的核心不是“自己实现”，而是“组织一群 Worker 实现并持续比较”。

建议流程：

1. 读取 `candidates.json`。
2. 为每个候选方案创建私有目录。
3. 通过 `spawn` 启动等数量的 Worker。
4. 传给每个 Worker：
   - 自己负责的 candidate id
   - 私有目录路径
   - 黑板路径
   - 议程路径
   - 当前轮次要求
5. 等待 Worker 完成本轮输出。
6. 汇总黑板，提炼：
   - 共同优势
   - 共同失败
   - 可借鉴技巧
   - 潜在融合机会
7. 更新 `agenda.json`。
8. 继续下一轮。
9. 三轮后选择最优候选或构造融合候选。
10. 组织最终综合报告并送 Reviewer。

## 20. Worker 的详细工作流

每个 Worker 在每一轮都遵循同一协议。

### 20.1 本轮开始前

读取：

- 自己的方案说明
- 当前轮次议程
- 公共黑板中其他 Worker 的最新条目

### 20.2 实现与实验

执行：

1. 修改代码或实验配置。
2. 运行实验。
3. 记录结果。
4. 写完整私有报告。

### 20.3 摘要抽取

从完整报告中抽取协作级摘要，只保留：

- 最关键假设
- 本轮关键改动
- 主指标
- 主要优势
- 主要弱点
- 可迁移经验
- 下一步建议

### 20.4 同行分析

基于黑板读取其他 Worker 的摘要后：

1. 判断别人的强项是什么。
2. 判断别人的弱点是什么。
3. 判断哪些点值得借鉴。
4. 判断如何把这些点转化成自己下一轮的改进动作。

### 20.5 黑板更新

更新：

- 自己的 `workers.<candidate_id>` 条目
- 自己对别人的 `peer_feedback.*` 条目

## 21. Reviewer 的详细工作流

Reviewer 主 Agent 只做一件事：

- 根据验收标准，用工具做客观核查

### 21.1 Reviewer 的输入

- `plan/acceptance_spec.json`
- `synthesis/final_report.md`
- `deliverables/`
- `shared/worker_board.json`
- 必要的私有实验产物路径

### 21.2 Reviewer 的审查方式

Reviewer 必须用现有工具完成核查：

1. `read_file`
   - 检查验收标准、最终报告、指标文件
2. `list_dir`
   - 检查交付是否完整
3. `exec`
   - 复现关键实验或至少复现关键评测脚本
4. `read_file + exec`
   - 对比报告中的结论与实际输出

### 21.3 评审结果

如果通过：

- 写 `review/review_report.md`
- 写 `review/review_feedback.json`
- 标明 `approved: true`

如果不通过：

- 写 `review/review_feedback.json`
- 明确 `must_fix`
- Implementer 读取后继续发起下一轮议程

## 22. 验收标准设计

Planner 必须先定义验收标准，Reviewer 只能按标准审查。

建议标准结构如下：

```json
{
  "hard_requirements": [
    "final code can run",
    "main experiment can be reproduced",
    "report uses actual measured metrics",
    "best solution outperforms baseline or clearly justifies failure"
  ],
  "soft_requirements": [
    "solution is modular",
    "discussion rounds produce meaningful improvement",
    "shared blackboard records transferable insights"
  ],
  "review_checks": [
    {
      "name": "reproduce_main_metric",
      "tool": "exec",
      "required": true
    },
    {
      "name": "verify_report_metric_consistency",
      "tool": "read_file",
      "required": true
    }
  ]
}
```

## 23. Skills 中的角色协议建议

### 23.1 `research-planner` 的协议重点

Planner 必须做到：

1. 先检索再拆解。
2. 生成多个候选，而不是单方案直冲。
3. 验收标准必须早于实现阶段。

### 23.2 `research-worker` 的协议重点

Worker 必须做到：

1. 完整报告写私有目录。
2. 公共黑板只写关键协作信息。
3. 下一轮改进必须明确说明：
   - 借鉴了谁
   - 借鉴了什么
   - 为什么借鉴

### 23.3 `research-reviewer` 的协议重点

Reviewer 必须做到：

1. 用工具核查，不凭主观放行。
2. 不合格时必须给出可执行打回项。
3. 结论必须可追踪到文件与命令。

## 24. 为什么该方案是“动态多智能体系统”

它的动态性体现在：

1. 候选数量由 Planner 在 3 到 5 之间动态决定。
2. Worker 之间的信息交互不是固定 pipeline，而是基于黑板当前内容动态发生。
3. 议程内容会随实验结果动态变化。
4. 打回后可以进入新的协作议程，而不是固定状态回退。
5. Implementer 可以根据黑板判断：
   - 保留哪个候选
   - 弱化哪个候选
   - 是否需要融合两个候选的优点

因此，这套系统的核心是：

- 公共知识黑板驱动的群体演化

而不是：

- 一个写死的阶段状态机

## 25. 最优解如何产生

最优解不应当来自“某个 Worker 自称自己最好”，而应当来自以下综合过程：

1. 各 Worker 的本轮指标
2. 各 Worker 在黑板上的强弱项
3. 同行反馈中反复被认可的可迁移技巧
4. Implementer 对群体模式的综合判断
5. Reviewer 的最终验收结果

建议最优解的形成方式有两种：

### 25.1 单候选胜出

如果某个候选：

- 主指标最好
- 风险较小
- 被同行多次认可其关键设计

则该候选直接成为最优解。

### 25.2 融合候选胜出

如果不同候选在不同维度有明显优势：

- 候选 A 的检索好
- 候选 B 的实验稳定
- 候选 C 的成本低

那么 Implementer 可以组织生成一个融合解。

融合解的来源依据必须来自黑板中被反复验证的“transferable_insights”，而不是凭空组合。

## 26. 不修改核心架构的实现建议

本节直接回答如何“真正落地”且不改核心代码。

### 26.1 允许做的事

可以做：

1. 新增 Skills。
2. 修改 Skills。
3. 在 Skills 目录中新增辅助脚本。
4. 通过现有工具读写共享 JSON。
5. 用现有 `spawn` 拉起 Worker。

### 26.2 不允许做的事

不应做：

1. 修改 `AgentLoop`
2. 修改 `SubagentManager`
3. 修改 `AgentRunner`
4. 修改 `SessionManager`
5. 修改核心 CLI 框架
6. 新增依赖核心注册逻辑的新内建机制

### 26.3 如果需要辅助能力怎么办

如果协作需要辅助功能，例如：

- 黑板校验
- peer feedback 合并
- 候选排序

应当通过以下方式解决：

1. 在 Skill 附带脚本中实现
2. 由 Agent 用现有 `exec` 调用脚本
3. 仍通过现有 `read_file` / `write_file` / `edit_file` 管理工件

这样就能在“不改内核”的前提下扩展能力。

## 27. 推荐的技能化落地方案

建议分为两层：

### 27.1 角色技能

- `research-planner`
- `research-implementer`
- `research-worker`
- `research-reviewer`

### 27.2 协议技能

- `research-blackboard`
- `research-report-digest`
- `research-peer-feedback`
- `research-final-synthesis`

角色技能告诉 Agent：

- 你是谁
- 你该做什么

协议技能告诉 Agent：

- 你该如何与其他 Agent 交换信息

## 28. 一次完整运行示例

输入需求：

```text
请设计一套多智能体科研系统，自动探索提升代码研究任务规划质量的方法。
```

系统流程：

1. Planner 检索相关论文与项目。
2. Planner 生成 4 个候选方案。
3. Planner 写出 `acceptance_spec.json`、`worker_board.json`、`agenda.json`。
4. Implementer 用 `spawn` 拉起 4 个 Worker。
5. 每个 Worker 在自己的目录实现并实验。
6. 每个 Worker 只把关键摘要写入 `worker_board.json`。
7. 其余 Worker 读取黑板，写入结构化 `peer_feedback`。
8. Implementer 汇总黑板，写出下一轮议程。
9. 重复三轮。
10. Implementer 形成最优候选或融合候选。
11. Reviewer 用 `exec` 与 `read_file` 做验收。
12. 若不通过，则 Reviewer 写 `review_feedback.json`。
13. Implementer 读取打回项，继续组织下一轮议程。
14. 若通过，则输出最终交付。

## 29. 该方案相对旧版设计的修正点

相较于旧版设计，本版做了以下关键修正：

1. 删除了对核心架构扩展层的依赖。
2. 删除了以状态机为核心的实现方式。
3. 不再建议新增研究编排 Python 核心模块。
4. 将系统实现重心转移到 `tools + skills + 共享工件协议`。
5. 强化了“Worker 不共享全文，只共享关键信息”的机制。
6. 明确引入公共 JSON 黑板作为协作中心。
7. 强调用动态议程而不是状态图来推进群体协作。

## 30. 最终推荐方案

在你给出的约束下，最合理、最稳妥、且真正能落到当前 `nanobot` 上的方案是：

1. 保持 `nanobot` 核心运行时完全不动。
2. 使用现有 `spawn + 文件工具 + exec + web 工具 + skills`。
3. 通过 Skills 定义 Planner / Implementer / Worker / Reviewer 四类角色协议。
4. 通过 `worker_board.json` 构建 Worker 间的公共协作黑板。
5. 通过 `agenda.json` 驱动动态协作，而不是状态机。
6. 通过“完整私有报告 + 公共关键摘要”实现信息隔离与协作复用。
7. 通过 Reviewer 基于工具的验收实现闭环打回。

这是一套真正符合“不能改核心架构、只能基于 tools 与 skills 设计”的动态多智能体科研系统方案。

## 31. 参考资料

1. nanobot 当前能力边界：
   - `nanobot/agent/subagent.py`
   - `nanobot/agent/tools/spawn.py`
   - `nanobot/agent/runner.py`
   - `nanobot/agent/loop.py`
   - `nanobot/session/manager.py`
2. ColaCare 仓库：
   - https://github.com/PKU-AICare/ColaCare
3. ColaCare 协作入口：
   - https://raw.githubusercontent.com/PKU-AICare/ColaCare/main/collaboration_pipeline.py
4. ColaCare 框架实现：
   - https://raw.githubusercontent.com/PKU-AICare/ColaCare/main/utils/framework.py
5. ColaCare 论文：
   - https://arxiv.org/abs/2410.02551
