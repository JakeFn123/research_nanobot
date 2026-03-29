## Purpose
Define acceptance-gate review behavior and redo loop semantics in the research delivery chain.

## Requirements
### Requirement: Reviewer returns evidence-backed decision
Reviewer SHALL output approved status, must-fix items, and tool evidence for each review request.

#### Scenario: Reviewer evaluates submission
- **WHEN** Implementer submits a review request
- **THEN** Reviewer returns structured decision payload with evidence lines

### Requirement: Rejected reviews trigger redo assignment
Implementer MUST decompose reviewer must-fix items into redo tasks and route them to the responsible workers.

#### Scenario: Review is rejected
- **WHEN** reviewer decision is rejected
- **THEN** Implementer creates redo tasks and starts another improvement round
