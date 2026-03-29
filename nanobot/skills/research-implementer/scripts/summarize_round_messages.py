from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from inbox_lib import _jsonl_read, inbox_file
from research_board_lib import save_json


def _normalize_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    out.append(text)
        return out
    return []


def _top_phrases(groups: list[list[str]], limit: int = 5) -> list[str]:
    counter: Counter[str] = Counter()
    original: dict[str, str] = {}
    for group in groups:
        for item in group:
            key = item.strip().lower()
            if not key:
                continue
            counter[key] += 1
            original.setdefault(key, item.strip())
    return [original[key] for key, _ in counter.most_common(limit)]


def summarize_round_messages(
    *,
    run_dir: Path,
    round_index: int,
    output_path: Path,
) -> dict[str, Any]:
    inbox_root = run_dir / "runtime" / "inbox"
    implementer_rows = _jsonl_read(inbox_file(inbox_root, "implementer"))

    updates: dict[str, dict[str, Any]] = {}
    strengths_groups: list[list[str]] = []
    failure_groups: list[list[str]] = []

    for row in implementer_rows:
        if str(row.get("type", "")) != "worker_round_update":
            continue
        if int(row.get("round", -1) or -1) != round_index:
            continue
        payload = row.get("payload", {})
        if not isinstance(payload, dict):
            continue

        candidate_id = str(payload.get("candidate_id", "")).strip()
        if not candidate_id:
            continue

        updates[candidate_id] = {
            "candidate_id": candidate_id,
            "owner": str(payload.get("owner", "")).strip(),
            "plan_name": str(payload.get("plan_name", "")).strip(),
            "round": int(payload.get("round", round_index) or round_index),
            "key_hypothesis": str(payload.get("key_hypothesis", "")).strip(),
            "core_metrics": payload.get("core_metrics", {}),
            "strengths": _normalize_lines(payload.get("strengths")),
            "weaknesses": _normalize_lines(payload.get("weaknesses")),
            "transferable_insights": _normalize_lines(payload.get("transferable_insights")),
            "open_problems": _normalize_lines(payload.get("open_problems")),
            "next_move": _normalize_lines(payload.get("next_move")),
            "private_report_ref": str(payload.get("private_report_ref", "")).strip(),
        }

    for item in updates.values():
        strengths_groups.append(item["strengths"])
        failure_groups.append(item["weaknesses"])
        failure_groups.append(item["open_problems"])

    improvement_targets: list[str] = []
    for row in implementer_rows:
        if int(row.get("round", -1) or -1) != round_index:
            continue
        if str(row.get("type", "")) != "improvement_proposal":
            continue
        payload = row.get("payload", {})
        if not isinstance(payload, dict):
            continue
        improvement_targets.extend(_normalize_lines(payload.get("suggested_improvement")))

    rank_rows: list[dict[str, Any]] = []
    for candidate_id, item in updates.items():
        metrics = item.get("core_metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}
        primary = metrics.get("primary_metric")
        try:
            primary_value = float(primary)
        except (TypeError, ValueError):
            primary_value = None
        rank_rows.append(
            {
                "candidate_id": candidate_id,
                "primary_metric": primary_value,
                "praise_score": len(item.get("strengths", [])),
                "concern_score": len(item.get("weaknesses", [])) + len(item.get("open_problems", [])),
            }
        )

    rank_rows.sort(
        key=lambda row: (
            row["primary_metric"] is None,
            -(row["primary_metric"] or 0.0),
            -row["praise_score"],
            row["concern_score"],
        )
    )

    summary = {
        "run_id": run_dir.name,
        "round": round_index,
        "candidate_summaries": updates,
        "candidate_rank_hint": rank_rows,
        "dominant_strengths": _top_phrases(strengths_groups, limit=5),
        "dominant_failures": _top_phrases(failure_groups, limit=5),
        "improvement_targets": _top_phrases([improvement_targets], limit=5),
        "message_count": len(updates),
    }

    save_json(output_path, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize one round from implementer inbox updates.")
    parser.add_argument("--run-dir", required=True, help="Run directory.")
    parser.add_argument("--round", required=True, type=int, help="Round index.")
    parser.add_argument("--output", required=True, help="Output summary JSON path.")
    args = parser.parse_args()

    summarize_round_messages(
        run_dir=Path(args.run_dir),
        round_index=args.round,
        output_path=Path(args.output),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
