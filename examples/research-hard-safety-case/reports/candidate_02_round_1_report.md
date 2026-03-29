## Key Hypothesis
Constitutional debate plus formal policy checking can improve safety-utility Pareto quality over purely heuristic filtering.

## Implementation Delta
- Added dual-agent constitutional debate with contradiction tracing.
- Added symbolic policy checker for high-risk action templates.

## Strengths
- Better policy consistency under adversarial paraphrase.
- Stronger utility retention than heavy blocking strategies.

## Weaknesses
- Debate overhead increases tail latency.
- Symbolic checker misses novel latent attack intents.

## Transferable Insights
- Contradiction tracing improves reviewer explainability.
- Policy-check artifacts support audit readiness.

## Open Problems
- Requires richer policy primitives for emerging threats.
- Cross-domain generalization remains fragile.

## Proposed Next Move
- Expand policy primitive library with mined adversarial motifs.
- Add adaptive debate depth controller.
