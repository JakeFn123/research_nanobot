from __future__ import annotations

import argparse
from pathlib import Path

from research_board_lib import ensure_board_shape, load_json, validate_feedback_entry, validate_worker_entry


def validate_board(board_path: Path) -> None:
    board = ensure_board_shape(load_json(board_path))
    ownership = board.get("worker_ownership", {})
    for candidate_id, entry in board["workers"].items():
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("Worker candidate ids must be non-empty strings.")
        if not isinstance(entry, dict):
            raise ValueError(f"Worker entry for '{candidate_id}' must be an object.")
        validate_worker_entry(entry)
        expected_owner = str(ownership.get(candidate_id, "")).strip()
        entry_owner = str(entry.get("owner", "")).strip()
        if expected_owner and entry_owner and expected_owner != entry_owner:
            raise ValueError(
                f"Ownership mismatch for '{candidate_id}': worker_ownership='{expected_owner}', entry.owner='{entry_owner}'."
            )
    for feedback_key, entry in board["peer_feedback"].items():
        if "_on_" not in feedback_key:
            raise ValueError(f"Peer feedback key '{feedback_key}' must include '_on_'.")
        if not isinstance(entry, dict):
            raise ValueError(f"Peer feedback '{feedback_key}' must be an object.")
        validate_feedback_entry(entry)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate worker_board.json structure.")
    parser.add_argument("--board", required=True, help="Path to worker_board.json.")
    args = parser.parse_args()
    validate_board(Path(args.board))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
