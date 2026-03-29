from __future__ import annotations

import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[2]
import sys

BLACKBOARD_DIR = SCRIPT_DIR / "research-blackboard" / "scripts"
DIGEST_DIR = SCRIPT_DIR / "research-report-digest" / "scripts"

for directory in (BLACKBOARD_DIR, DIGEST_DIR):
    dir_str = str(directory)
    if dir_str not in sys.path:
        sys.path.insert(0, dir_str)

from digest_report import digest_report
from research_board_lib import ensure_board_shape, load_json
from worker_round_lib import ensure_notes_file, save_json, resolve_artifacts


def run_worker_round(
    run_dir: Path,
    candidate_id: str,
    round_index: int,
    owner: str,
    reports_root: Path | None,
    allow_fallback_rounds: bool,
    summary_out: Path,
) -> dict:
    board = ensure_board_shape(load_json(run_dir / "shared" / "worker_board.json"))
    if candidate_id not in board["workers"]:
        raise ValueError(f"Candidate '{candidate_id}' is not registered in worker_board.json.")

    plan_name = str(board["workers"][candidate_id].get("plan_name", candidate_id)).strip() or candidate_id
    report_path, metrics_path, used_round, used_fallback = resolve_artifacts(
        run_dir=run_dir,
        reports_root=reports_root,
        candidate_id=candidate_id,
        round_index=round_index,
        allow_fallback_rounds=allow_fallback_rounds,
    )

    digest_path = run_dir / "shared" / "pending_digests" / f"{candidate_id}_round_{round_index}.json"
    digest_report(
        report_path=report_path,
        metrics_path=metrics_path,
        candidate_id=candidate_id,
        plan_name=plan_name,
        round_index=round_index,
        owner=owner,
        output_path=digest_path,
        status="active",
    )

    notes_path = ensure_notes_file(
        run_dir=run_dir,
        candidate_id=candidate_id,
        round_index=round_index,
        used_round=used_round,
        used_fallback=used_fallback,
    )

    summary = {
        "candidate_id": candidate_id,
        "owner": owner,
        "round": round_index,
        "used_round": used_round,
        "used_fallback": used_fallback,
        "fallback_note": (
            f"{candidate_id}: requested round {round_index}, fallback to round {used_round}"
            if used_fallback
            else ""
        ),
        "digest_path": str(digest_path),
        "report_path": str(report_path),
        "metrics_path": str(metrics_path),
        "notes_path": str(notes_path),
    }
    save_json(summary_out, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one worker round and generate digest artifacts.")
    parser.add_argument("--run-dir", required=True, help="Path to run directory.")
    parser.add_argument("--candidate-id", required=True, help="Candidate id.")
    parser.add_argument("--round", required=True, type=int, help="Round index.")
    parser.add_argument("--owner", required=True, help="Worker owner id.")
    parser.add_argument("--reports-root", help="Optional external reports dir.")
    parser.add_argument(
        "--allow-fallback-rounds",
        action="store_true",
        help="Allow fallback to latest available round artifacts if exact round files are missing.",
    )
    parser.add_argument("--summary-out", required=True, help="Summary output json path.")
    args = parser.parse_args()

    run_worker_round(
        run_dir=Path(args.run_dir),
        candidate_id=args.candidate_id,
        round_index=args.round,
        owner=args.owner,
        reports_root=Path(args.reports_root) if args.reports_root else None,
        allow_fallback_rounds=args.allow_fallback_rounds,
        summary_out=Path(args.summary_out),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
