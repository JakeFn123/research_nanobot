## Purpose
Define the end-to-end multi-agent research flow for this project using role-based collaboration and iterative delivery.

## Requirements
### Requirement: Planner publishes executable plan bundle
Planner SHALL publish an executable plan bundle that includes candidate solutions and acceptance criteria before implementation starts.

#### Scenario: Planner hands off plan bundle
- **WHEN** a new research run starts
- **THEN** Planner outputs candidates and acceptance spec artifacts for Implementer

### Requirement: Implementer orchestrates workers in iterative rounds
Implementer SHALL assign one candidate to each worker and orchestrate at least three iterative rounds unless Reviewer approves earlier.

#### Scenario: Implementer starts round execution
- **WHEN** plan bundle is ready
- **THEN** Implementer dispatches worker tasks by candidate and round

### Requirement: System publishes final package
The system SHALL publish a final package containing conclusion, review evidence, and pipeline summary.

#### Scenario: Final package is generated
- **WHEN** Reviewer returns approval
- **THEN** final conclusion and supporting deliverables are written to deliverables
