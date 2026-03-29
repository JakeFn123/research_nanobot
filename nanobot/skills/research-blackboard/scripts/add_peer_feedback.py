from __future__ import annotations

import argparse
from pathlib import Path

from research_board_lib import ensure_board_shape, load_json, save_json, validate_feedback_entry


def add_peer_feedback(
    board_path: Path,
    from_candidate: str,
    to_candidate: str,
    feedback_path: Path,
    actor: str | None = None,
) -> None:
    board = ensure_board_shape(load_json(board_path))
    if from_candidate == to_candidate:
        raise ValueError("from_candidate and to_candidate must be different.")
    if from_candidate not in board["workers"]:
        raise ValueError(f"Unknown from_candidate '{from_candidate}'.")
    if to_candidate not in board["workers"]:
        raise ValueError(f"Unknown to_candidate '{to_candidate}'.")

    actor_name = (actor or "").strip()
    ownership = board.get("worker_ownership", {})
    expected_owner = str(ownership.get(from_candidate, "")).strip() or str(
        board["workers"][from_candidate].get("owner", "")
    ).strip()
    if expected_owner and actor_name and actor_name != expected_owner:
        raise ValueError(
            f"Actor '{actor_name}' is not allowed to publish feedback for '{from_candidate}' (owner '{expected_owner}')."
        )

    feedback = validate_feedback_entry(load_json(feedback_path))
    key = f"{from_candidate}_on_{to_candidate}"
    board["peer_feedback"][key] = feedback
    save_json(board_path, board)


def main() -> int:
    parser = argparse.ArgumentParser(description="Insert or update one peer feedback entry in worker_board.json.")
    parser.add_argument("--board", required=True, help="Path to worker_board.json.")
    parser.add_argument("--from-candidate", required=True, help="Feedback author candidate id.")
    parser.add_argument("--to-candidate", required=True, help="Feedback target candidate id.")
    parser.add_argument("--feedback-file", required=True, help="Path to peer feedback json file.")
    parser.add_argument("--actor", help="Worker owner identity performing this write.")
    args = parser.parse_args()
    add_peer_feedback(
        Path(args.board),
        args.from_candidate,
        args.to_candidate,
        Path(args.feedback_file),
        actor=args.actor,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
