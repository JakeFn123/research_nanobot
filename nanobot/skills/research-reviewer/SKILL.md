---
name: research-reviewer
description: Review a research run against acceptance criteria using existing tools only. Use when validating final outputs, reproducing key checks, and generating revision feedback without changing nanobot core runtime.
---

# Research Reviewer

Use this skill when you are the final reviewer for a research run.

## Review Inputs

Read:

- `plan/acceptance_spec.json`
- `shared/worker_board.json`
- `synthesis/final_report.md`
- `deliverables/`
- any private candidate files needed for verification

## Required Behavior

1. Use tools, do not rely on subjective approval.
2. Reproduce key checks with `exec` when possible.
3. Verify report claims against actual files.
4. If the result is not good enough, write actionable revision feedback.

## Required Outputs

- `review/review_report.md`
- `review/review_feedback.json`

## Review Feedback Shape

```json
{
  "approved": false,
  "must_fix": [
    "..."
  ],
  "optional_improvements": [
    "..."
  ],
  "evidence": [
    "..."
  ]
}
```

## Important Constraint

Do not accept a result just because the narrative sounds strong. Approval must be grounded in tool-based evidence.

## Automation Script

Use the reviewer script to generate standardized review artifacts:

```bash
python nanobot/skills/research-reviewer/scripts/review_run.py \
  --board "<run_dir>/shared/worker_board.json" \
  --agenda "<run_dir>/shared/agenda.json" \
  --acceptance "<run_dir>/plan/acceptance_spec.json" \
  --output-feedback "<run_dir>/review/review_feedback.json" \
  --output-report "<run_dir>/review/review_report.md"
```
