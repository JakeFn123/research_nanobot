---
name: research-implementer
description: Coordinate dynamic multi-agent research execution using existing tools, spawn workers, shared JSON blackboards, and agenda files. Use when running or iterating a research run without modifying nanobot core code.
---

# Research Implementer

Use this skill when you are orchestrating a research run after planning is complete.

## Core Responsibilities

1. Read `plan/candidates.json`.
2. Spawn one worker per candidate.
3. Keep workers isolated in their own directories.
4. Drive collaboration through:
   - `shared/worker_board.json`
   - `shared/agenda.json`
5. Never ask workers to broadcast their full reports to peers.
6. Update the agenda after each round based on board content.

## Worker Spawn Pattern

Spawn one worker per candidate and pass:

- candidate id
- private directory
- blackboard path
- agenda path
- current round objective

Use the current `spawn` tool. Do not depend on runtime changes.

## Round Loop

For each round:

1. Wait for workers to finish their private implementation and blackboard updates.
2. Validate the board:

```bash
python nanobot/skills/research-blackboard/scripts/validate_board.py \
  --board "<run_dir>/shared/worker_board.json"
```

3. Refresh global findings:

```bash
python nanobot/skills/research-blackboard/scripts/synthesize_findings.py \
  --board "<run_dir>/shared/worker_board.json"
```

4. Generate the next dynamic agenda:

```bash
python nanobot/skills/research-blackboard/scripts/generate_agenda.py \
  --board "<run_dir>/shared/worker_board.json" \
  --agenda "<run_dir>/shared/agenda.json" \
  --max-rounds 3
```

## Review Loop

If reviewer feedback exists, include it when generating the next agenda:

```bash
python nanobot/skills/research-blackboard/scripts/generate_agenda.py \
  --board "<run_dir>/shared/worker_board.json" \
  --agenda "<run_dir>/shared/agenda.json" \
  --review-feedback "<run_dir>/review/review_feedback.json" \
  --max-rounds 3
```

## Important Constraint

Do not redesign the runtime. Treat the run as a protocol executed through files, tools, and skills.

## Automation Script

For local end-to-end protocol execution (planner -> implementer -> reviewer -> conclusion), use:

```bash
python nanobot/skills/research-implementer/scripts/run_full_cycle.py \
  --run-root "<workspace>/research_runs" \
  --run-id "<run_id>" \
  --problem "<problem statement>" \
  --reports-root "<reports_dir>" \
  --candidates-file "<optional candidates.json>" \
  --acceptance-file "<optional acceptance_spec.json>"
```

This script only uses skill-layer scripts and shared artifacts. It does not modify nanobot core runtime.
