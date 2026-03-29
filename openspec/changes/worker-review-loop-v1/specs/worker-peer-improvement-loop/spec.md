## ADDED Requirements

### Requirement: Workers exchange structured peer insights
Workers SHALL exchange peer_key_insight messages with strengths, weaknesses, and transferable insights for each candidate round.

#### Scenario: Cross-worker feedback is posted
- **WHEN** a worker consumes another worker's round update
- **THEN** it sends a structured peer insight message for actionable improvement

### Requirement: Workers record adoption and rejection outcomes
Workers MUST report adopted_from_peers and rejected_peer_suggestions in the next round update.

#### Scenario: Worker reports next iteration decision
- **WHEN** worker submits next round update
- **THEN** payload includes what was adopted, what was rejected, and resulting impact
