from __future__ import annotations

import argparse
from pathlib import Path

from research_board_lib import ensure_board_shape, load_json, save_json, validate_worker_entry


def upsert_worker_entry(board_path: Path, candidate_id: str, entry_path: Path, actor: str | None = None) -> None:
    board = ensure_board_shape(load_json(board_path))
    if candidate_id not in board["workers"]:
        raise ValueError(
            f"Candidate '{candidate_id}' is not registered in board workers. Initialize run slots first."
        )

    entry = validate_worker_entry(load_json(entry_path))
    actor_name = (actor or "").strip()
    ownership = board.get("worker_ownership", {})
    expected_owner = str(ownership.get(candidate_id, "")).strip()
    existing_owner = str(board["workers"][candidate_id].get("owner", "")).strip()
    proposed_owner = str(entry.get("owner", "")).strip()

    resolved_owner = expected_owner or existing_owner or proposed_owner or actor_name
    if not resolved_owner:
        raise ValueError(
            f"Cannot resolve owner for '{candidate_id}'. Provide owner in entry or --actor."
        )
    if expected_owner and proposed_owner and proposed_owner != expected_owner:
        raise ValueError(
            f"Owner mismatch for '{candidate_id}': expected '{expected_owner}', got '{proposed_owner}'."
        )
    if actor_name and actor_name != resolved_owner:
        raise ValueError(
            f"Actor '{actor_name}' is not allowed to update '{candidate_id}' (owner '{resolved_owner}')."
        )

    entry["owner"] = resolved_owner
    board["workers"][candidate_id] = entry
    board["worker_ownership"][candidate_id] = resolved_owner
    board["round_index"] = max(int(board.get("round_index", 0) or 0), int(entry.get("round", 0) or 0))
    save_json(board_path, board)


def main() -> int:
    parser = argparse.ArgumentParser(description="Insert or update one worker entry in worker_board.json.")
    parser.add_argument("--board", required=True, help="Path to worker_board.json.")
    parser.add_argument("--candidate-id", required=True, help="Candidate slot to update.")
    parser.add_argument("--entry-file", required=True, help="Path to one worker entry json file.")
    parser.add_argument("--actor", help="Worker owner identity performing this write.")
    args = parser.parse_args()
    upsert_worker_entry(Path(args.board), args.candidate_id, Path(args.entry_file), actor=args.actor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
