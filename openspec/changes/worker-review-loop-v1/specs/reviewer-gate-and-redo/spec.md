## MODIFIED Requirements

### Requirement: Rejected reviews trigger redo assignment
Implementer MUST decompose reviewer must-fix items into redo tasks, route each redo task to responsible workers, and start a new improvement round before resubmitting review.

#### Scenario: Must-fix items become runnable tasks
- **WHEN** reviewer decision is rejected with must-fix items
- **THEN** implementer emits redo_task_assigned messages mapped by candidate and owner
