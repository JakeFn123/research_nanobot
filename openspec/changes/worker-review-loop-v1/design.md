## Context
Worker discussion quality determines final convergence quality. Current behavior needs a standardized loop for cross-worker feedback and reviewer-driven redo cycles.

## Goals / Non-Goals

**Goals:**
- Standardize peer insight exchange.
- Ensure must-fix items become executable redo tasks.
- Preserve evidence trail for accept/reject decisions.

**Non-Goals:**
- Expanding into autonomous long-running schedulers.
- Sharing full private worker reports among peers.

## Decisions
- Add explicit peer_key_insight and improvement_proposal message semantics.
- Require Implementer to map reviewer must_fix to candidate-scoped redo tasks.
- Require each worker to emit adoption/rejection outcomes next round.

## Risks / Trade-offs
- [Risk] More protocol messages may increase noise → Mitigation: fixed payload schema and required fields only.
- [Risk] Incorrect redo routing may stall iteration → Mitigation: deterministic candidate mapping in redo assignment tool.
