## Key Hypothesis
Red-team self-play with a neuro-symbolic runtime monitor can drive the best robustness under adaptive attacks without catastrophic utility loss.

## Implementation Delta
- Added attacker-defender self-play loop with exploit memory.
- Added neuro-symbolic monitor for runtime risk scoring and intervention.

## Strengths
- Fast adaptation to unseen jailbreak variants.
- Best overall robustness with high-quality outputs.

## Weaknesses
- System complexity and tuning cost are high.
- Early versions showed unstable intervention frequency.

## Transferable Insights
- Exploit memory accelerates hard-negative discovery.
- Runtime risk calibration can be reused across candidates.

## Open Problems
- Need simpler deployment defaults for production teams.
- Need stronger guarantees under distribution drift.

## Proposed Next Move
- Ship calibrated default profiles and fail-safe escalation ladder.
- Run larger drift-focused benchmark suite.
