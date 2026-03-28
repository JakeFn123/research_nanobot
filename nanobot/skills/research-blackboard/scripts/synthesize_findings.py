from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from research_board_lib import (
    concern_score,
    ensure_board_shape,
    incoming_feedback,
    load_json,
    normalize_lines,
    praise_score,
    save_json,
    top_phrases,
)


def _candidate_rank_hint(board: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate_id, entry in board["workers"].items():
        metrics = entry.get("core_metrics", {})
        rows.append(
            {
                "candidate_id": candidate_id,
                "primary_metric": metrics.get("primary_metric"),
                "praise_score": praise_score(board, candidate_id),
                "concern_score": concern_score(board, candidate_id),
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            item["primary_metric"] is None,
            -(item["primary_metric"] or 0.0),
            -item["praise_score"],
            item["concern_score"],
        ),
    )


def synthesize_findings(board_path: Path) -> dict[str, Any]:
    board = ensure_board_shape(load_json(board_path))

    strength_groups: list[list[str]] = []
    failure_groups: list[list[str]] = []
    improvement_groups: list[list[str]] = []
    fusion_opportunities: list[dict[str, Any]] = []

    for candidate_id, entry in board["workers"].items():
        strengths = normalize_lines(entry.get("strengths"))
        weaknesses = normalize_lines(entry.get("weaknesses"))
        insights = normalize_lines(entry.get("transferable_insights"))
        problems = normalize_lines(entry.get("open_problems"))

        strength_groups.append(strengths)
        failure_groups.append(weaknesses)
        failure_groups.append(problems)

        if insights:
            fusion_opportunities.append(
                {
                    "candidate_id": candidate_id,
                    "plan_name": entry.get("plan_name", ""),
                    "transferable_insights": insights[:3],
                }
            )

        for feedback in incoming_feedback(board, candidate_id):
            strength_groups.append(normalize_lines(feedback.get("observed_strengths")))
            failure_groups.append(normalize_lines(feedback.get("observed_weaknesses")))
            improvement_groups.append(normalize_lines(feedback.get("suggested_improvement")))
            improvement_groups.append(normalize_lines(feedback.get("borrowable_ideas")))

    board["global_findings"] = {
        "dominant_strengths": top_phrases(strength_groups, limit=5),
        "dominant_failures": top_phrases(failure_groups, limit=5),
        "candidate_rank_hint": _candidate_rank_hint(board),
        "fusion_opportunities": fusion_opportunities[:5],
        "improvement_targets": top_phrases(improvement_groups, limit=5),
    }
    save_json(board_path, board)
    return board["global_findings"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive global findings from worker_board.json.")
    parser.add_argument("--board", required=True, help="Path to worker_board.json.")
    args = parser.parse_args()
    synthesize_findings(Path(args.board))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
