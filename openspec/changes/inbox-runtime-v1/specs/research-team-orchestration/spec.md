## MODIFIED Requirements

### Requirement: Implementer orchestrates workers in iterative rounds
Implementer SHALL assign one candidate to each worker and orchestrate iterative rounds using inbox event routing with correlation-id tracking until Reviewer approves.

#### Scenario: Implementer coordinates by inbox events
- **WHEN** planner handoff is received
- **THEN** Implementer dispatches worker tasks and tracks round progress through inbox messages
