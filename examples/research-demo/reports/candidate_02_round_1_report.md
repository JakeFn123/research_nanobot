## Key Hypothesis
Use a lightweight ranking heuristic to keep plan quality acceptable while reducing latency and cost.

## Implementation Delta
- added cheap candidate ranking before final plan selection
- removed expensive retrieval from the first draft

## Strengths
- low latency
- low cost

## Weaknesses
- weaker grounding
- more unstable rejection of weak plans

## Transferable Insights
- cheap ranking can prune obvious bad candidates
- low-cost filtering is useful before deep analysis

## Open Problems
- misses hard negative plans

## Proposed Next Move
- borrow stronger filtering from candidate_01
- add one selective retrieval step
