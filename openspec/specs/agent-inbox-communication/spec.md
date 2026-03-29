## Purpose
Define asynchronous agent-to-agent communication contracts using per-agent inboxes and structured messages.

## Requirements
### Requirement: Each role uses a dedicated inbox channel
The system SHALL provide a dedicated inbox stream for each role (Planner, Implementer, Reviewer, and each Worker).

#### Scenario: Agent reads assigned messages
- **WHEN** an agent polls communication state
- **THEN** it reads only messages addressed to its role inbox

### Requirement: Message envelope is mandatory and typed
Every inter-agent message MUST include run_id, round, from, to, type, correlation_id, ts_utc, and payload fields.

#### Scenario: Message is validated before enqueue
- **WHEN** a sender posts an event
- **THEN** the event is accepted only if mandatory envelope fields are present

### Requirement: Worker shares only key insights
Workers SHALL share key structured insights and artifact references, and MUST NOT broadcast full private reports in inbox messages.

#### Scenario: Worker posts round update
- **WHEN** a worker finishes a round
- **THEN** the update includes key metrics and insights plus private report reference only
