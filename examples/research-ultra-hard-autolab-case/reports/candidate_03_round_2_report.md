## Key Hypothesis
Adversarial specialist debate plus verifier consensus improves mechanistic correctness under shift.

## Implementation Delta
- Round 2: Debate-Verifier Mechanistic Ensemble integrated peer feedback from all other workers and tightened reviewer-facing evidence packaging.
- Added stronger uncertainty-aware gating for expensive wet-lab runs and improved fallback controls for unstable regimes.

## Strengths
- Strong mechanistic interpretability with explicit disagreement audits
- Better transfer of high-value findings into cross-worker proposals in round 2.

## Weaknesses
- Higher coordination overhead and longer iteration latency
- Remaining tension between exploration depth and strict safety thresholds.

## Transferable Insights
- Verifier checkpoints sharply reduce unsupported mechanism claims
- Structured key-insight exchange improved convergence speed without leaking private full reports.

## Open Problems
- Need adaptive pruning to control debate branch explosion
- Need a stronger closed-loop benchmark with adversarial perturbation scenarios.

## Proposed Next Move
- Prioritize experiments maximizing expected information gain under hard safety constraints.
- Reduce uncertainty while keeping budget growth sublinear in round-to-round scaling.
