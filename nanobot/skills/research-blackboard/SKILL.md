---
name: research-blackboard
description: Maintain the shared worker board, agenda, and final conclusion files for dynamic multi-agent research collaboration. Use when initializing runs, validating board structure, publishing worker summaries, merging peer feedback, generating the next agenda, and finalizing results.
---

# Research Blackboard

Use this skill whenever the run depends on:

- `shared/worker_board.json`
- `shared/agenda.json`

## Shared Files

- `worker_board.json`
  - worker summaries
  - peer feedback
  - global findings
- `agenda.json`
  - the next dynamic actions
- `deliverables/final_conclusion.json`
  - final structured conclusion for delivery
- `deliverables/final_conclusion.md`
  - readable final conclusion summary

## Available Scripts

Initialize a run:

```bash
python nanobot/skills/research-blackboard/scripts/init_research_run.py --help
```

Validate the board:

```bash
python nanobot/skills/research-blackboard/scripts/validate_board.py --help
```

Upsert one worker summary:

```bash
python nanobot/skills/research-blackboard/scripts/upsert_worker_entry.py --help
```

Add peer feedback:

```bash
python nanobot/skills/research-blackboard/scripts/add_peer_feedback.py --help
```

Synthesize global findings:

```bash
python nanobot/skills/research-blackboard/scripts/synthesize_findings.py --help
```

Generate the next agenda:

```bash
python nanobot/skills/research-blackboard/scripts/generate_agenda.py --help
```

Generate final conclusion artifacts:

```bash
python nanobot/skills/research-blackboard/scripts/finalize_conclusion.py --help
```

## Board Rules

1. Each worker owns only its own entry under `workers.<candidate_id>`.
   Use `--actor` when calling write scripts to enforce ownership.
2. Peer feedback keys must be shaped like `<from>_on_<to>`.
3. Global findings are derived, not hand-written.
4. Keep the board high-signal. Never paste a full report into it.
