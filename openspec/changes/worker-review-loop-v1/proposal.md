## Why
The system already supports review and redo, but worker-to-worker improvement discussions need explicit spec coverage to make iterative optimization consistent and auditable.

## What Changes
- **worker-peer-improvement-loop:** add structured peer insight and improvement proposal exchange across workers.
- **reviewer-gate-and-redo:** refine redo routing behavior to ensure must-fix items are decomposed and re-assigned deterministically.

## Capabilities

### New Capabilities
- `worker-peer-improvement-loop`: define peer discussion artifacts and adoption/rejection trace fields.

### Modified Capabilities
- `reviewer-gate-and-redo`: strengthen rejected-review handling with explicit redo assignment semantics.

## Impact
- Affected scripts: implementer coordination and reviewer feedback routing tools
- Affected docs: multi-agent design and inbox protocol
- Affected outputs: round synthesis summaries and redo task messages
