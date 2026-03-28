---
name: research-report-digest
description: Extract high-signal structured collaboration summaries from private worker reports and metrics files. Use when workers need to share key findings without exposing their full reports.
---

# Research Report Digest

Use this skill after a worker has produced a private report.

## Goal

Convert a full private report into a structured digest suitable for the shared board.

## Script

```bash
python nanobot/skills/research-report-digest/scripts/digest_report.py --help
```

## Required Report Sections

The digest script expects these headings:

- `## Key Hypothesis`
- `## Implementation Delta`
- `## Strengths`
- `## Weaknesses`
- `## Transferable Insights`
- `## Open Problems`
- `## Proposed Next Move`

## Metrics Input

Prefer a metrics JSON shaped like:

```json
{
  "primary_metric": 0.71,
  "secondary_metrics": {
    "latency_ms": 920,
    "cost_usd": 0.84
  }
}
```

If your metrics file uses `primary` and `secondary`, the script also accepts that.
