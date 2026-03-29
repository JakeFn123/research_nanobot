# Debug V2 与后端通信启发（落地说明）

本文档总结本次基于高质量多智能体 debug 轨迹得到的改造启发，并说明在 `research_nanobot` 中的落地实现。

## 1. 主要启发

从参考调试轨迹可见，真正高可用的多智能体系统不只需要“步骤日志”，还需要：

1. **多 lane 观测模型**：主代理、子代理、调度器分 lane，才能定位协作瓶颈。
2. **成对事件**：`begin/end` 成对记录，才能精确计算耗时和识别未闭合调用。
3. **调用链可追踪**：`call_id + message_id + reply_to` 三键组合，可重建消息线程。
4. **双层日志**：
   - 宏观层：pipeline/lane 事件流；
   - 微观层：通信线程与回包健康度。
5. **健康诊断输出**：除了日志本身，要直接给出异常摘要（open calls / orphan replies）。

## 2. 本项目落地改造

### 2.1 Debug Trace Schema 升级到 v2

文件：

- `nanobot/skills/research-implementer/scripts/debug_trace.py`

新增能力：

1. `schema_version = runtime_trace_v2`
2. lane 注册与输出（`lanes`）
3. 事件增强字段：
   - `event_id/event_type/phase/lane_id/agent_name/agent_kind`
   - `call_id/message_id/reply_to_message_id`
   - `start_time_utc/end_time_utc/duration_ms`
4. summary 聚合：
   - `status_counts/event_type_counts/phase_counts/lane_counts`
   - `open_call_count/invalid_phase_events`
5. 健康度文件：
   - `debug/runtime_trace_health.json`

### 2.2 消息信封增强

文件：

- `nanobot/skills/research-implementer/scripts/inbox_lib.py`

新增字段：

1. `call_id`
2. `thread_id`

效果：

1. 每条消息具备调用链关联键；
2. thread 粒度分析成为可能（不仅仅是 correlation 粒度）。

### 2.3 run_inbox_cycle 通信埋点升级

文件：

- `nanobot/skills/research-implementer/scripts/run_inbox_cycle.py`

新增能力：

1. lane 注册（planner/implementer/reviewer/workers/system）
2. 统一消息发送封装 `_publish_message(...)`
   - 自动产出 `message.send.<type>` begin/end 事件
   - 记录 call_id、耗时、message_id、reply_to
3. 新增线程诊断产物：
   - `debug/message_threads.json`
4. `pipeline_summary_inbox.json` 新增调试输出路径：
   - `debug_trace_health_json`
   - `debug_message_threads_json`
   - `debug_trace_schema_version`

### 2.4 UI 可观测性升级

文件：

- `apps/research_team_interactive_ui.py`

新增能力：

1. `步骤调试 I/O` 支持按 `lane/event_type/phase/call_id/message_id` 过滤
2. 新增 `通信线程` 页签，直接展示：
   - thread 数量与消息规模
   - reply 边数量
   - orphan reply（断链回复）
3. `交付结果` 增加：
   - `runtime_trace_health.json`
   - `message_threads.json`

## 3. 对后端架构的启发

1. **后端应以“可观测契约”设计，而非仅功能契约**：
   - 每个核心动作都有统一 trace envelope；
   - 所有通信具备 thread/call 关联键。
2. **诊断输出应结构化**：
   - 让自动验收工具可直接判断健康状态；
   - 减少人工看日志成本。
3. **消息系统应“线程优先”**：
   - correlation 用于任务域聚合；
   - thread/reply 用于对话链与回包正确性验证。

## 4. 对 Agent 交流模式的启发

1. **请求模板标准化**（Context/Goal/Boundaries/Output Contract）
2. **回复模板标准化**（证据、结论、后续动作、风险）
3. **协作动作可审计**（spawn/interact/wait/timeout 成对记录）
4. **回复必须可回链**（reply_to 不能为空的场景应制度化）

## 5. 下一步建议

1. 为 `route_review_feedback` 与 `review_inbox_run` 也补齐 begin/end 与 lane 埋点
2. 增加 `orphan_reply == 0` 的 CI 检查
3. 在 Reviewer 侧引入“通信质量阈值”作为 soft gate（如 open calls、超时比例）

