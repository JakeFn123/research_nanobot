from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from research_board_lib import ensure_board_shape, incoming_feedback, load_json, normalize_lines, save_json


def _active_candidates(board: dict[str, Any]) -> list[str]:
    active: list[str] = []
    for candidate_id, entry in board["workers"].items():
        if str(entry.get("status", "active")).strip() not in {"dropped", "archived", "failed"}:
            active.append(candidate_id)
    return active


def _worker_actions(board: dict[str, Any], review_feedback: dict[str, Any] | None) -> dict[str, list[str]]:
    actions: dict[str, list[str]] = {}
    findings = board.get("global_findings", {})

    for candidate_id, entry in board["workers"].items():
        if candidate_id not in _active_candidates(board):
            continue
        candidate_actions: list[str] = []
        candidate_actions.extend(normalize_lines(entry.get("proposed_next_move")))

        for feedback in incoming_feedback(board, candidate_id):
            candidate_actions.extend(normalize_lines(feedback.get("suggested_improvement")))

        for target in normalize_lines(findings.get("improvement_targets"))[:2]:
            if target not in candidate_actions:
                candidate_actions.append(target)

        if review_feedback and not review_feedback.get("approved", False):
            candidate_actions.extend(normalize_lines(review_feedback.get("must_fix")))

        if not candidate_actions:
            candidate_actions.append("Run one focused improvement based on the strongest peer insight.")

        deduped: list[str] = []
        seen: set[str] = set()
        for item in candidate_actions:
            normalized = item.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(item.strip())
        actions[candidate_id] = deduped[:5]
    return actions


def generate_agenda(
    board_path: Path,
    agenda_path: Path,
    review_feedback_path: Path | None = None,
    max_rounds: int = 3,
) -> dict[str, Any]:
    board = ensure_board_shape(load_json(board_path))
    review_feedback = load_json(review_feedback_path) if review_feedback_path else None
    current_round = int(board.get("round_index", 0) or 0)

    if review_feedback and not review_feedback.get("approved", False):
        next_round = current_round + 1
        ready_for_review = False
    elif current_round >= max_rounds:
        next_round = current_round
        ready_for_review = True
    else:
        next_round = current_round + 1
        ready_for_review = False

    findings = board.get("global_findings", {})
    priority_questions = []
    priority_questions.extend(normalize_lines(findings.get("dominant_failures"))[:3])
    priority_questions.extend(normalize_lines(findings.get("improvement_targets"))[:2])
    if review_feedback and not review_feedback.get("approved", False):
        priority_questions.extend(normalize_lines(review_feedback.get("must_fix"))[:3])
    if not priority_questions:
        priority_questions = [
            "Which candidate should absorb the strongest transferable insight next?",
            "Which weakness most threatens final acceptance?",
        ]

    agenda = {
        "round_index": next_round,
        "ready_for_review": ready_for_review,
        "active_candidates": _active_candidates(board),
        "priority_questions": priority_questions,
        "worker_actions": _worker_actions(board, review_feedback),
    }
    save_json(agenda_path, agenda)
    return agenda


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the next dynamic agenda from worker_board.json.")
    parser.add_argument("--board", required=True, help="Path to worker_board.json.")
    parser.add_argument("--agenda", required=True, help="Output path for agenda.json.")
    parser.add_argument("--review-feedback", help="Optional reviewer feedback json path.")
    parser.add_argument("--max-rounds", type=int, default=3, help="Maximum pre-review rounds.")
    args = parser.parse_args()
    generate_agenda(
        board_path=Path(args.board),
        agenda_path=Path(args.agenda),
        review_feedback_path=Path(args.review_feedback) if args.review_feedback else None,
        max_rounds=args.max_rounds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
