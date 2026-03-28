---
name: research-planner
description: Plan research tasks under the dynamic multi-agent workflow. Use when the user wants to turn a fuzzy research idea into 3-5 candidate plans, acceptance criteria, and shared run files without changing nanobot core runtime.
---

# Research Planner

Use this skill when you are the planning role for a research run.

## Goals

1. Clarify the research problem.
2. Search for relevant papers, repos, and benchmarks.
3. Produce 3-5 candidate approaches.
4. Define acceptance criteria before implementation starts.
5. Initialize the shared run directory and blackboard files.

## Required Outputs

Write these files under the selected run directory:

- `plan/plan_brief.md`
- `plan/candidates.json`
- `plan/acceptance_spec.json`

Then initialize the shared workspace with:

```bash
python nanobot/skills/research-blackboard/scripts/init_research_run.py \
  --root "<workspace>/research_runs" \
  --run-id "<run_id>" \
  --problem "<problem statement>" \
  --candidates-file "<run_dir>/plan/candidates.json" \
  --acceptance-file "<run_dir>/plan/acceptance_spec.json"
```

## Candidate Rules

Each candidate should include:

- `candidateId`
- `name`
- `hypothesis`
- `implementationSpec`
- `expectedBenefits`
- `risks`

Keep candidates distinct. Do not create superficial variants.

## Acceptance Rules

Acceptance criteria must be tool-checkable. Prefer:

- runnable code
- reproducible experiment commands
- measured metrics
- baseline comparison or explicit failure analysis

## Important Constraint

Do not propose any implementation that requires changing nanobot core runtime.
All later execution must be possible through existing tools plus skills.
