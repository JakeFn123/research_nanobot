## Why
To optimize day-to-day design and development flow, operators need immediate visibility into inbox traffic and runtime traces from the local UI.

## What Changes
- **streamlit-inbox-debug-panel:** add UI-level inbox inspection and message filtering for run debugging.
- **runtime-observability:** extend observability to include inbox flow checkpoints alongside pipeline step traces.

## Capabilities

### New Capabilities
- `streamlit-inbox-debug-panel`: provide operator-facing inbox inspection panel in local Streamlit UI.

### Modified Capabilities
- `runtime-observability`: include inbox flow markers in trace outputs.

## Impact
- Affected app: Streamlit local UI
- Affected artifacts: runtime trace and inbox debug outputs
- Affected workflow: troubleshooting and acceptance verification speed
