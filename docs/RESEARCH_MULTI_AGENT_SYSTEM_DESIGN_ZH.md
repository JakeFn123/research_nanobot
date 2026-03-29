# 基于 nanobot 的科研多智能体系统设计（Agent Team + Inbox，无共享黑板）

## 1. 设计目标

在不修改 `nanobot` 核心架构的前提下（不改 `AgentLoop/Runner/SubagentManager/SessionManager`），基于 `tools + skills + spawn` 构建可落地的科研闭环系统，满足：

1. 规划者将模糊需求拆为可验收标准与 3-5 个可执行方案。
2. 实现者并行调度多个 Worker，进行三轮实现、讨论、迭代优化。
3. 评审者基于工具证据验收，不通过则打回重做，直至形成最优解。
4. Worker 间不共享完整报告，仅共享关键结论与改进建议。
5. 不采用共享黑板（`worker_board.json`）作为协作中心。

## 2. 参考模式与核心原则

本设计参考 `learn-claude-code` 的 Agent Team / Inbox 思路（`s09-agent-teams`）：

1. 角色常驻：每个子 Agent 有稳定身份与职责。
2. 消息驱动：通过 inbox 进行异步通信，而非共享状态对象。
3. 拉取处理：Agent 从 inbox 读取分配给自己的消息后处理，再发送回复。
4. 最小共享：只共享结构化关键事实，不共享完整私有工件。
5. 动态协作：按消息事件驱动推进，不做固定状态机编排。

## 3. 角色架构

系统由 4 类角色组成：

1. `PlannerLead`（规划主 Agent）
2. `ImplementerLead`（实现主 Agent）
3. `Worker_i`（实现子 Agent，数量 = 候选方案数量）
4. `ReviewerLead`（评审主 Agent）

职责划分：

1. `PlannerLead`
   - 检索相关研究与基线
   - 输出 `candidates.json` 与 `acceptance_spec.json`
   - 向 `ImplementerLead` 下发执行包
2. `ImplementerLead`
   - 拉起 N 个 `Worker_i`
   - 分发候选方案与轮次任务
   - 组织跨 Worker 讨论与融合
   - 汇总轮次结论并提交评审
3. `Worker_i`
   - 按指定候选方案实现与实验
   - 产出私有完整报告（仅本 Worker 可见）
   - 对外仅发布结构化关键摘要（inbox 消息）
4. `ReviewerLead`
   - 基于验收标准执行工具检查
   - 输出 `approved / must_fix / evidence`
   - 不通过时将打回意见发回 `ImplementerLead`

## 4. 通信模型（无共享黑板）

### 4.1 Inbox 模型

每个 Agent 拥有独立 inbox：

1. `runtime/inbox/planner.jsonl`
2. `runtime/inbox/implementer.jsonl`
3. `runtime/inbox/worker_01.jsonl ... worker_n.jsonl`
4. `runtime/inbox/reviewer.jsonl`

每条消息是独立 JSON 事件，append-only 存储。Agent 通过“读取自己的 inbox -> 处理 -> 发新消息”推进协作。

### 4.2 消息信封（统一协议）

```json
{
  "id": "msg_20260328_000123",
  "run_id": "run_xxx",
  "round": 2,
  "from": "worker_02",
  "to": "implementer",
  "type": "worker_round_update",
  "priority": "normal",
  "correlation_id": "task_worker_02_r2",
  "reply_to": "msg_20260328_000099",
  "ts_utc": "2026-03-28T10:10:10Z",
  "payload": {},
  "artifacts": []
}
```

字段约束：

1. `type` 必填，驱动处理路由。
2. `correlation_id` 必填，用于串联一个任务链路。
3. `payload` 只放关键结构化信息，不放完整长文。
4. `artifacts` 只放私有产物路径引用，不复制大文件内容。

### 4.3 关键消息类型

1. `plan_bundle_ready`
2. `worker_task_assigned`
3. `worker_round_update`
4. `peer_key_insight`
5. `improvement_proposal`
6. `round_synthesis_ready`
7. `review_request`
8. `review_result_approved`
9. `review_result_rejected`
10. `redo_task_assigned`
11. `final_package_ready`

## 5. Worker 间讨论模式（只交换关键结论）

每轮中，`Worker_i` 发送 `worker_round_update`，`payload` 固定为：

```json
{
  "candidate_id": "candidate_02",
  "key_hypothesis": "...",
  "core_metrics": {
    "primary_metric": 0.78,
    "secondary_metrics": {
      "faithfulness": 0.86,
      "novelty": 0.71
    }
  },
  "strengths": ["..."],
  "weaknesses": ["..."],
  "transferable_insights": ["..."],
  "open_problems": ["..."],
  "next_move": ["..."],
  "private_report_ref": "implementation/candidate_02/round_2/report.md"
}
```

讨论约束：

1. 不发送完整报告正文。
2. 其他 Worker 只读取 `key_hypothesis / metrics / strengths / weaknesses / insights / next_move`。
3. 反馈必须结构化为 `peer_key_insight` 或 `improvement_proposal`。
4. 每轮至少包含“采纳了什么、拒绝了什么、为什么、效果如何”。

## 6. 动态闭环流程（事件驱动，不是状态机）

### 阶段 A：规划

1. `PlannerLead` 研究并产生 `candidates.json` + `acceptance_spec.json`。
2. 发送 `plan_bundle_ready` 给 `ImplementerLead`。

### 阶段 B：并行实现（3 轮）

1. `ImplementerLead` 按候选数创建 `Worker_i`。
2. 下发 `worker_task_assigned`（每个 Worker 绑定一个候选方案）。
3. 每个 Worker 完成该轮实现并上报 `worker_round_update`。
4. `ImplementerLead` 将关键结论转发为跨 Worker 的 `peer_key_insight`。
5. Worker 基于他人关键结论回发 `improvement_proposal`。
6. `ImplementerLead` 聚合并产出 `round_synthesis_ready`。
7. 重复共 3 轮。

### 阶段 C：评审与打回

1. `ImplementerLead` 发送 `review_request` 到 `ReviewerLead`。
2. `ReviewerLead` 用工具验证并返回：
   - `review_result_approved`，或
   - `review_result_rejected`（含 `must_fix` + `evidence`）。
3. 若 rejected，`ImplementerLead` 将 `must_fix` 拆解成 `redo_task_assigned` 下发 Worker，再进入下一轮迭代。

### 阶段 D：收敛与交付

1. 评审通过后，`ImplementerLead` 生成最终融合结论。
2. 发送 `final_package_ready`。
3. 输出最终工件（总结报告、结论、证据清单）。

## 7. 数据与工件分层

### 私有层（Worker 私有）

1. 完整实验日志
2. 完整实验报告
3. 代码与脚本细节

### 协作层（Inbox 消息）

1. 关键假设
2. 指标摘要
3. 强弱项
4. 可迁移洞见
5. 下一步动作
6. 私有工件引用路径

### 交付层（面向验收）

1. `review_feedback.json`
2. `review_report.md`
3. `final_conclusion.json`
4. `final_conclusion.md`
5. `pipeline_summary.json`
6. `runtime_trace.jsonl / runtime_trace.md`

## 8. 与原共享黑板方案的差异

1. 不再依赖 `worker_board.json` 作为中心协作数据结构。
2. 协作状态由 inbox 消息链与 `correlation_id` 驱动。
3. 聚合信息由 `ImplementerLead` 在消费消息时即时生成，不要求全局共享可变对象。
4. 通信更贴近真实多 Agent 异步协作，降低共享文件并发冲突。

## 9. 工程落地边界（符合当前约束）

仍遵守你的约束：

1. 不改 nanobot 核心运行时。
2. 仅在 `tools/skills` 层实现团队编排与 inbox 通信工具。
3. 维持 Worker “只共享关键结论，不共享完整报告”的协作规则。
4. 通过工具化评审闭环保障可验收性。

## 10. 小结

该设计把“共享黑板协作”升级为“Agent Team + Inbox 协作”：

1. 角色清晰
2. 通信可追踪
3. 讨论可结构化复用
4. 打回与重做可编排
5. 在不动核心内核的前提下，能实现动态科研多智能体闭环

## 11. 参考

1. Agent Team / Inbox 参考文档：
   - https://github.com/shareAI-lab/learn-claude-code/blob/main/docs/en/s09-agent-teams.md
