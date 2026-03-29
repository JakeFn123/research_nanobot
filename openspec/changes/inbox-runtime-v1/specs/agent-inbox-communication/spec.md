## ADDED Requirements

### Requirement: Inbox message uses canonical envelope
Every inbox message MUST include id, run_id, round, from, to, type, correlation_id, ts_utc, and payload.

#### Scenario: Sender enqueues a message
- **WHEN** any role posts a workflow event
- **THEN** the message is accepted only if the canonical envelope is complete

### Requirement: Worker updates exclude full private report bodies
Worker update messages SHALL contain key structured insights and private_report_ref, and MUST NOT include full report body text.

#### Scenario: Worker publishes round update
- **WHEN** worker sends worker_round_update
- **THEN** payload includes key insight fields and report reference only
