from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parents[2]
import sys

BLACKBOARD_DIR = SCRIPT_DIR / "research-blackboard" / "scripts"
if str(BLACKBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(BLACKBOARD_DIR))

from research_board_lib import ensure_board_shape, load_json
from worker_round_lib import build_feedback_from_entry, save_json


def _is_active(entry: dict[str, Any]) -> bool:
    status = str(entry.get("status", "active")).strip().lower()
    return status not in {"dropped", "archived", "failed"}


def run_peer_feedback(
    run_dir: Path,
    from_candidate: str,
    round_index: int,
    summary_out: Path,
) -> dict:
    board = ensure_board_shape(load_json(run_dir / "shared" / "worker_board.json"))
    workers = board.get("workers", {})
    if from_candidate not in workers:
        raise ValueError(f"from_candidate '{from_candidate}' is not registered in board workers.")

    owner = str(workers[from_candidate].get("owner", "")).strip() or str(
        board.get("worker_ownership", {}).get(from_candidate, "")
    ).strip()
    feedback_rows: list[dict[str, str]] = []
    out_dir = run_dir / "shared" / "pending_peer_feedback" / f"round_{round_index}"

    for to_candidate, to_entry in workers.items():
        if to_candidate == from_candidate:
            continue
        if not isinstance(to_entry, dict):
            continue
        if not _is_active(to_entry):
            continue
        payload = build_feedback_from_entry(to_entry)
        target_path = out_dir / f"{from_candidate}_on_{to_candidate}.json"
        save_json(target_path, payload)
        feedback_rows.append(
            {
                "to_candidate": to_candidate,
                "feedback_path": str(target_path),
            }
        )

    summary = {
        "from_candidate": from_candidate,
        "owner": owner,
        "round": round_index,
        "feedback_files": feedback_rows,
    }
    save_json(summary_out, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate peer feedback files for one worker.")
    parser.add_argument("--run-dir", required=True, help="Path to run directory.")
    parser.add_argument("--from-candidate", required=True, help="Feedback author candidate id.")
    parser.add_argument("--round", required=True, type=int, help="Round index.")
    parser.add_argument("--summary-out", required=True, help="Summary output json path.")
    args = parser.parse_args()

    run_peer_feedback(
        run_dir=Path(args.run_dir),
        from_candidate=args.from_candidate,
        round_index=args.round,
        summary_out=Path(args.summary_out),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
