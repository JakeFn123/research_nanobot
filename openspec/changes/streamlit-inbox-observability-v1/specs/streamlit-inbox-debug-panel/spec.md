## ADDED Requirements

### Requirement: UI exposes inbox stream inspection
The local UI SHALL provide an inbox debug panel that loads planner, implementer, reviewer, and worker inbox streams for a selected run.

#### Scenario: Operator opens inbox debug view
- **WHEN** operator navigates to inbox debug panel
- **THEN** UI shows parsed message rows from all available inbox JSONL files

### Requirement: UI supports operational filters
The inbox debug panel MUST support filtering by run_id, role, round, and message type.

#### Scenario: Operator filters noisy message stream
- **WHEN** operator applies filters
- **THEN** UI returns only rows matching selected criteria
