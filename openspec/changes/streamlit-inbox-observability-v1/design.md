## Context
The project already has runtime trace files, but debugging complex inbox-driven team workflows still requires opening multiple files manually.

## Goals / Non-Goals

**Goals:**
- Expose inbox events in local UI for quick diagnosis.
- Link inbox checkpoints with runtime trace events.
- Improve operator confidence during end-to-end test runs.

**Non-Goals:**
- Building a production-grade distributed monitoring stack.
- Replacing structured JSONL trace artifacts.

## Decisions
- Add a Streamlit tab dedicated to inbox message inspection.
- Keep JSONL as source of truth and render filtered views in UI.
- Emit inbox send/read checkpoints in runtime traces for correlation.

## Risks / Trade-offs
- [Risk] UI panel could become noisy on long runs → Mitigation: run-id, role, round, and type filters.
- [Risk] Duplicate visibility channels (UI + files) can diverge → Mitigation: UI reads directly from artifact files.
