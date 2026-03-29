## Context
The project already has a completed blackboard-style workflow and now requires an inbox-based communication model. The transition must happen without modifying nanobot core runtime.

## Goals / Non-Goals

**Goals:**
- Enforce a stable inbox message envelope.
- Shift orchestration semantics to event-driven inbox routing.
- Keep worker outputs minimal and structured.

**Non-Goals:**
- Rewriting core nanobot loop/session subsystems.
- Introducing centralized mutable shared board state.

## Decisions
- Use append-only per-role JSONL inbox streams.
- Require correlation_id for every message to track task lineage.
- Keep private reports out of inbox payload and send only path references.

## Risks / Trade-offs
- [Risk] More message files increase operational complexity → Mitigation: strict naming and validation rules.
- [Risk] Missing correlation IDs break traceability → Mitigation: reject invalid envelopes on write.
