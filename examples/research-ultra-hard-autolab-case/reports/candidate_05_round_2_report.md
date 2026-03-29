## Key Hypothesis
Hierarchical RL with hard constraints yields best long-horizon performance under safety and budget limits.

## Implementation Delta
- Round 2: Hierarchical RL + Constraint Guardian integrated peer feedback from all other workers and tightened reviewer-facing evidence packaging.
- Added stronger uncertainty-aware gating for expensive wet-lab runs and improved fallback controls for unstable regimes.

## Strengths
- Best global objective optimization across quality/safety/cost
- Better transfer of high-value findings into cross-worker proposals in round 2.

## Weaknesses
- Policy warm-up requires stronger priors in early rounds
- Remaining tension between exploration depth and strict safety thresholds.

## Transferable Insights
- Constraint guardian prevents unsafe exploration without crippling learning
- Structured key-insight exchange improved convergence speed without leaking private full reports.

## Open Problems
- Need continual policy adaptation for hardware maintenance drift
- Need a stronger closed-loop benchmark with adversarial perturbation scenarios.

## Proposed Next Move
- Prioritize experiments maximizing expected information gain under hard safety constraints.
- Reduce uncertainty while keeping budget growth sublinear in round-to-round scaling.
