## Key Hypothesis
Progressive adversarial curriculum plus retrieval guardrails can reduce jailbreak success while keeping utility stable.

## Implementation Delta
- Added attack-family-balanced curriculum and citation-anchored retrieval sanitizer.
- Added context-window trust scoring for long-context segment routing.

## Strengths
- Strong grounding reduces unsafe free-form generations.
- Reproducibility artifacts are clear and modular.

## Weaknesses
- Novel exploit classes still bypass static sanitizer rules.
- Safety gain slows under highly compositional attacks.

## Transferable Insights
- Trust-scored context segmentation transfers to other defenses.
- Curriculum balancing improves stability across seeds.

## Open Problems
- Guardrails still rely on hand-tuned thresholds.
- Latency spikes under worst-case retrieval fan-out.

## Proposed Next Move
- Learn threshold policies from attack traces.
- Introduce dynamic retrieval budget under uncertainty.
