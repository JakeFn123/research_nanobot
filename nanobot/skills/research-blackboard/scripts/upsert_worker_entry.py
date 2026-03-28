from __future__ import annotations

import argparse
from pathlib import Path

from research_board_lib import ensure_board_shape, load_json, save_json, validate_worker_entry


def upsert_worker_entry(board_path: Path, candidate_id: str, entry_path: Path) -> None:
    board = ensure_board_shape(load_json(board_path))
    entry = validate_worker_entry(load_json(entry_path))
    board["workers"][candidate_id] = entry
    board["round_index"] = max(int(board.get("round_index", 0) or 0), int(entry.get("round", 0) or 0))
    save_json(board_path, board)


def main() -> int:
    parser = argparse.ArgumentParser(description="Insert or update one worker entry in worker_board.json.")
    parser.add_argument("--board", required=True, help="Path to worker_board.json.")
    parser.add_argument("--candidate-id", required=True, help="Candidate slot to update.")
    parser.add_argument("--entry-file", required=True, help="Path to one worker entry json file.")
    args = parser.parse_args()
    upsert_worker_entry(Path(args.board), args.candidate_id, Path(args.entry_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
