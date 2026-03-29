## MODIFIED Requirements

### Requirement: Pipeline emits step-level runtime trace
The system SHALL write structured runtime trace entries for major pipeline steps and MUST include inbox send/read checkpoints with correlation identifiers.

#### Scenario: Trace captures orchestration checkpoints
- **WHEN** implementer routes inbox tasks and workers consume them
- **THEN** runtime trace contains checkpoint events linking pipeline steps to inbox flow
