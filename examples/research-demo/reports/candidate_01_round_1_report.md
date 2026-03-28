## Key Hypothesis
Use retrieval before decomposition so the planner sees stronger references before it commits to a structure.

## Implementation Delta
- added retrieval before drafting the plan
- ranked retrieved evidence before final decomposition

## Strengths
- strong grounding from external references
- better rejection of weak candidate directions

## Weaknesses
- slower end-to-end latency
- extra retrieval cost

## Transferable Insights
- retrieval-first flow helps eliminate weak ideas early
- ranking evidence before decomposition improves stability

## Open Problems
- diversity drops when retrieval is too narrow

## Proposed Next Move
- reduce retrieval cost
- widen evidence diversity
