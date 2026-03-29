from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from inbox_lib import send_message
from research_board_lib import extract_candidates, load_json, save_json

CANDIDATE_ID_RE = re.compile(r"\bcandidate_\d{2}\b")


def _candidate_worker_map(candidates_payload: Any) -> dict[str, str]:
    rows = extract_candidates(candidates_payload)
    mapping: dict[str, str] = {}
    for index, row in enumerate(rows, start=1):
        candidate_id = str(row.get("candidateId") or row.get("candidate_id") or "").strip()
        if not candidate_id:
            continue
        mapping[candidate_id] = f"worker_{index:02d}"
    return mapping


def route_review_feedback(
    *,
    run_dir: Path,
    review_feedback_path: Path,
    round_index: int,
    output_path: Path,
) -> dict[str, Any]:
    review = load_json(review_feedback_path)
    if not isinstance(review, dict):
        raise ValueError("review feedback must be a JSON object")

    must_fix_raw = review.get("must_fix")
    if isinstance(must_fix_raw, str):
        must_fix = [must_fix_raw.strip()] if must_fix_raw.strip() else []
    elif isinstance(must_fix_raw, list):
        must_fix = [str(item).strip() for item in must_fix_raw if str(item).strip()]
    else:
        must_fix = []

    plan_candidates = load_json(run_dir / "plan" / "candidates.json")
    candidate_to_worker = _candidate_worker_map(plan_candidates)
    candidate_ids = list(candidate_to_worker.keys())

    inbox_root = run_dir / "runtime" / "inbox"
    routed_rows: list[dict[str, Any]] = []

    for idx, item in enumerate(must_fix, start=1):
        matched_candidates = sorted(set(CANDIDATE_ID_RE.findall(item.lower())))
        targets = [cid for cid in matched_candidates if cid in candidate_to_worker]
        if not targets:
            targets = candidate_ids

        for candidate_id in targets:
            worker_role = candidate_to_worker[candidate_id]
            payload = {
                "candidate_id": candidate_id,
                "must_fix_item": item,
                "redo_task": f"Address reviewer must-fix #{idx}: {item}",
            }
            message = send_message(
                inbox_root=inbox_root,
                run_id=run_dir.name,
                round_index=round_index,
                from_role="implementer",
                to_role=worker_role,
                message_type="redo_task_assigned",
                correlation_id=f"redo_r{round_index}_{candidate_id}_{idx}",
                payload=payload,
                priority="high",
                artifacts=[str(review_feedback_path)],
            )
            routed_rows.append(
                {
                    "candidate_id": candidate_id,
                    "worker": worker_role,
                    "must_fix_item": item,
                    "message_id": message["id"],
                }
            )

    summary = {
        "run_id": run_dir.name,
        "round": round_index,
        "must_fix_count": len(must_fix),
        "routed_count": len(routed_rows),
        "routes": routed_rows,
    }
    save_json(output_path, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Route reviewer must-fix items to worker redo tasks.")
    parser.add_argument("--run-dir", required=True, help="Run directory.")
    parser.add_argument("--review-feedback", required=True, help="review_feedback.json path.")
    parser.add_argument("--round", required=True, type=int, help="Redo round index.")
    parser.add_argument("--output", required=True, help="Routing summary JSON path.")
    args = parser.parse_args()

    route_review_feedback(
        run_dir=Path(args.run_dir),
        review_feedback_path=Path(args.review_feedback),
        round_index=args.round,
        output_path=Path(args.output),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
