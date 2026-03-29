# OpenSpec Playbook for research_nanobot

## 1) One-time setup

```bash
cd /Users/jakefan/nanobot
OPENSPEC_TELEMETRY=0 openspec init --tools codex --profile core
```

## 2) Baseline status

```bash
OPENSPEC_TELEMETRY=0 openspec list --specs
OPENSPEC_TELEMETRY=0 openspec list
```

## 3) Work changes in sequence

Current seeded changes:
1. `inbox-runtime-v1`
2. `worker-review-loop-v1`
3. `streamlit-inbox-observability-v1`

Inspect a change:

```bash
OPENSPEC_TELEMETRY=0 openspec show inbox-runtime-v1 --type change
OPENSPEC_TELEMETRY=0 openspec status --change inbox-runtime-v1 --json
```

## 4) Validation gate

```bash
OPENSPEC_TELEMETRY=0 openspec validate --all --strict
```

## 5) Daily workflow

1. Create change: `openspec new change <name>`
2. Fill `proposal.md` (why / capabilities / impact)
3. Add delta specs under `changes/<name>/specs/*/spec.md`
4. Fill `design.md` and `tasks.md`
5. Validate strict mode
6. Implement code
7. Re-validate and archive

## 6) Notes for this project

- This project now follows Team + Inbox design (no shared blackboard requirement).
- Keep worker messages concise and structured.
- Keep full private reports in artifacts, not in inbox payloads.
