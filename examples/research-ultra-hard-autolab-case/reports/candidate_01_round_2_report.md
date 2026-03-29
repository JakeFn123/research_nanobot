## Key Hypothesis
Bayesian active design with mechanistic priors maximizes gain-per-experiment under safety constraints.

## Implementation Delta
- Round 2: Physics-Informed Bayesian Lab Planner integrated peer feedback from all other workers and tightened reviewer-facing evidence packaging.
- Added stronger uncertainty-aware gating for expensive wet-lab runs and improved fallback controls for unstable regimes.

## Strengths
- Excellent uncertainty calibration for sparse experimental budgets
- Better transfer of high-value findings into cross-worker proposals in round 2.

## Weaknesses
- Can under-explore radical protocol shifts
- Remaining tension between exploration depth and strict safety thresholds.

## Transferable Insights
- Posterior-risk coupling improves safe candidate triage
- Structured key-insight exchange improved convergence speed without leaking private full reports.

## Open Problems
- Need stronger coupling between microkinetic and process-level simulators
- Need a stronger closed-loop benchmark with adversarial perturbation scenarios.

## Proposed Next Move
- Prioritize experiments maximizing expected information gain under hard safety constraints.
- Reduce uncertainty while keeping budget growth sublinear in round-to-round scaling.
