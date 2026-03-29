## Why
The current design docs moved to Team + Inbox collaboration, but the development workflow needs explicit OpenSpec change control so communication contracts and orchestration behavior stay consistent.

## What Changes
- **agent-inbox-communication:** add strict inbox envelope and worker key-insight exchange rules.
- **research-team-orchestration:** update orchestration requirement from shared-board-centric behavior to inbox-event-driven execution.

## Capabilities

### New Capabilities
- `agent-inbox-communication`: standardize per-agent inbox streams and typed message envelopes.

### Modified Capabilities
- `research-team-orchestration`: implementer coordination is message-driven and correlation-id based.

## Impact
- Affected docs: system design and communication protocol docs
- Affected scripts: research implementer/reviewer/planner skill scripts that route runtime data
- Affected runtime artifacts: inbox JSONL streams and trace outputs
