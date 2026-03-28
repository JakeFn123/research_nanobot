---
name: research-worker
description: Execute one research candidate in a private directory, write a full private report, publish only key information to the shared worker board, review peer summaries, and improve the candidate without sharing full reports.
---

# Research Worker

Use this skill when you are assigned a single candidate in a research run.

## Hard Rules

1. Work only in your own candidate directory.
2. Write the full implementation report privately.
3. Do not share the full report with other workers.
4. Publish only key structured information to the shared board.
5. Read other workers only through the shared board unless explicitly instructed otherwise.

## Private Outputs

For each round, write:

- `implementation/<candidate_id>/round_<n>/report.md`
- `implementation/<candidate_id>/round_<n>/metrics.json`
- `implementation/<candidate_id>/round_<n>/notes.md`

## Report Structure

Use these exact section headings in the private report so the digest script can parse them:

- `## Key Hypothesis`
- `## Implementation Delta`
- `## Strengths`
- `## Weaknesses`
- `## Transferable Insights`
- `## Open Problems`
- `## Proposed Next Move`

Use flat bullets inside the list-style sections.

## Publish a Digest to the Shared Board

After writing the private report and metrics file:

```bash
python nanobot/skills/research-report-digest/scripts/digest_report.py \
  --report "<private report path>" \
  --metrics "<metrics path>" \
  --candidate-id "<candidate_id>" \
  --plan-name "<plan name>" \
  --round <round_index> \
  --owner "<worker label>" \
  --output "<candidate digest json>"
```

Then upsert the board entry:

```bash
python nanobot/skills/research-blackboard/scripts/upsert_worker_entry.py \
  --board "<run_dir>/shared/worker_board.json" \
  --candidate-id "<candidate_id>" \
  --entry-file "<candidate digest json>"
```

## Peer Analysis

Read `shared/worker_board.json` and write peer feedback JSON files. Each feedback file must contain:

- `observed_strengths`
- `observed_weaknesses`
- `borrowable_ideas`
- `suggested_improvement`

Then publish the feedback:

```bash
python nanobot/skills/research-blackboard/scripts/add_peer_feedback.py \
  --board "<run_dir>/shared/worker_board.json" \
  --from-candidate "<your candidate id>" \
  --to-candidate "<peer candidate id>" \
  --feedback-file "<feedback json>"
```

## Improvement Rule

When iterating, explicitly state in `notes.md`:

- which peer idea you borrowed
- which peer idea you rejected
- what code or experiment changed
- whether the new result improved

## Script Helpers

For scripted protocol execution, worker-stage helpers are available:

```bash
python nanobot/skills/research-worker/scripts/run_worker_round.py --help
python nanobot/skills/research-worker/scripts/run_peer_feedback.py --help
```
