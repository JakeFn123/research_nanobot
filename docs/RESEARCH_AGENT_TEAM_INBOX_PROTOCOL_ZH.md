# Agent Team Inbox 通信协议（无共享黑板）

## 1. 协议目标

为科研多智能体系统提供统一的 Agent 间通信规范，支持：

1. 异步协作
2. 可追溯对话链路
3. 打回重做闭环
4. 仅共享关键结论，不共享完整报告

## 2. 目录约定

```text
runtime/
  inbox/
    planner.jsonl
    implementer.jsonl
    reviewer.jsonl
    worker_01.jsonl
    worker_02.jsonl
  artifacts/
    planner/
    implementer/
    reviewer/
    workers/
```

约定：

1. inbox 文件 append-only。
2. 每行一条 JSON 消息。
3. 完整报告放 `artifacts/workers/*`，消息仅传关键摘要与路径引用。

## 3. 消息 JSON Schema（逻辑字段）

```json
{
  "id": "msg_001",
  "run_id": "run_abc",
  "round": 1,
  "from": "implementer",
  "to": "worker_01",
  "type": "worker_task_assigned",
  "priority": "high",
  "correlation_id": "task_cand01_r1",
  "reply_to": "",
  "ts_utc": "2026-03-28T10:00:00Z",
  "payload": {},
  "artifacts": []
}
```

字段说明：

1. `id`：消息唯一 ID。
2. `run_id`：同一研究任务 ID。
3. `round`：当前轮次。
4. `from` / `to`：发送方与接收方。
5. `type`：消息类型（决定处理逻辑）。
6. `priority`：`high|normal|low`。
7. `correlation_id`：同一任务链路 ID（必须）。
8. `reply_to`：被回复消息 ID（可空）。
9. `payload`：结构化关键内容。
10. `artifacts`：相关工件路径列表。

## 4. 消息类型

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

## 5. Worker 更新负载规范

`worker_round_update.payload` 必须包含：

```json
{
  "candidate_id": "candidate_01",
  "key_hypothesis": "...",
  "core_metrics": {
    "primary_metric": 0.81,
    "secondary_metrics": {}
  },
  "strengths": ["..."],
  "weaknesses": ["..."],
  "transferable_insights": ["..."],
  "open_problems": ["..."],
  "next_move": ["..."],
  "adopted_from_peers": ["..."],
  "rejected_peer_suggestions": ["..."],
  "private_report_ref": "artifacts/workers/candidate_01/round_3/report.md"
}
```

限制：

1. 不允许在消息中嵌入完整报告正文。
2. 不允许超长自由文本讨论替代结构化字段。

## 6. 拉取与确认语义

建议语义：

1. `read_inbox(agent_id, limit)`：读取该 agent 未处理消息。
2. `ack_message(agent_id, message_id)`：处理完成确认。
3. `requeue_message(agent_id, message_id, reason)`：处理失败重入队列。

若暂不实现 ack 文件，可先采用“消费后写 processed index”的轻量方案。

## 7. 打回重做协议

评审拒绝时，`review_result_rejected.payload`：

```json
{
  "approved": false,
  "must_fix": ["..."],
  "evidence": ["..."],
  "deadline_hint": "2026-03-30T00:00:00Z"
}
```

`Implementer` 收到后：

1. 拆解 `must_fix` 为多个 `redo_task_assigned`。
2. 按候选方案路由到对应 Worker。
3. 进入下一轮迭代并再次提交评审。

## 8. 与共享黑板方案的边界

本协议明确：

1. 不依赖 `worker_board.json` 作为全局协作状态。
2. 协作关系由 inbox 消息链表达。
3. 聚合结果可写交付文件，但不作为共享可变黑板。

## 9. 最小可用实现建议（tools/skills 层）

建议新增/改造工具：

1. `send_message.py`
2. `read_inbox.py`
3. `ack_message.py`
4. `route_review_feedback.py`
5. `summarize_round_messages.py`

建议新增技能：

1. `research-team-orchestrator`
2. `research-worker-inbox`
3. `research-reviewer-inbox`

以上均可在 `tools/skills` 层落地，无需改动 nanobot 核心。
