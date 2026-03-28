from __future__ import annotations

import argparse
from pathlib import Path

from research_board_lib import ensure_board_shape, load_json, save_json, validate_feedback_entry


def add_peer_feedback(
    board_path: Path,
    from_candidate: str,
    to_candidate: str,
    feedback_path: Path,
) -> None:
    board = ensure_board_shape(load_json(board_path))
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
    args = parser.parse_args()
    add_peer_feedback(
        Path(args.board),
        args.from_candidate,
        args.to_candidate,
        Path(args.feedback_file),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
