## Key Hypothesis
Causal transport across labs improves generalization while reducing sample complexity.

## Implementation Delta
- Round 1: Causal Transfer Twin with Domain Adaptation integrated peer feedback from all other workers and tightened reviewer-facing evidence packaging.
- Added stronger uncertainty-aware gating for expensive wet-lab runs and improved fallback controls for unstable regimes.

## Strengths
- Best cross-domain transfer stability in low-data regimes
- Better transfer of high-value findings into cross-worker proposals in round 1.

## Weaknesses
- Transport assumptions can break under abrupt reactor drift
- Remaining tension between exploration depth and strict safety thresholds.

## Transferable Insights
- Invariant causal features improve out-of-lab reproducibility
- Structured key-insight exchange improved convergence speed without leaking private full reports.

## Open Problems
- Need online drift adaptation with confidence guarantees
- Need a stronger closed-loop benchmark with adversarial perturbation scenarios.

## Proposed Next Move
- Prioritize experiments maximizing expected information gain under hard safety constraints.
- Reduce uncertainty while keeping budget growth sublinear in round-to-round scaling.
