from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from research_board_lib import extract_candidates, load_json, save_json


def _candidate_id(index: int, candidate: dict[str, Any]) -> str:
    value = candidate.get("candidateId") or candidate.get("candidate_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return f"candidate_{index + 1:02d}"


def _candidate_name(candidate: dict[str, Any], fallback: str) -> str:
    for key in ("name", "title", "planName"):
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _initial_worker_entry(candidate_id: str, plan_name: str, hypothesis: str, owner: str) -> dict[str, Any]:
    return {
        "owner": owner,
        "plan_name": plan_name,
        "round": 0,
        "status": "pending",
        "key_hypothesis": hypothesis,
        "implementation_delta": [],
        "core_metrics": {
            "primary_metric": None,
            "secondary_metrics": {},
        },
        "strengths": [],
        "weaknesses": [],
        "transferable_insights": [],
        "open_problems": [],
        "proposed_next_move": [],
        "private_report_path": f"implementation/{candidate_id}/round_1/report.md",
    }


def init_research_run(
    root: Path,
    run_id: str,
    problem: str,
    candidates_file: Path,
    acceptance_file: Path | None = None,
    rounds: int = 3,
) -> Path:
    run_dir = root / run_id
    plan_dir = run_dir / "plan"
    shared_dir = run_dir / "shared"
    impl_dir = run_dir / "implementation"
    synthesis_dir = run_dir / "synthesis"
    review_dir = run_dir / "review"
    deliver_dir = run_dir / "deliverables"

    for path in (plan_dir, shared_dir, impl_dir, synthesis_dir, review_dir, deliver_dir):
        path.mkdir(parents=True, exist_ok=True)

    raw_candidates = load_json(candidates_file)
    candidates = extract_candidates(raw_candidates)

    workers: dict[str, dict[str, Any]] = {}
    worker_ownership: dict[str, str] = {}
    worker_actions: dict[str, list[str]] = {}
    active_candidates: list[str] = []

    for index, candidate in enumerate(candidates):
        candidate_id = _candidate_id(index, candidate)
        plan_name = _candidate_name(candidate, candidate_id)
        hypothesis = str(candidate.get("hypothesis", "")).strip()
        owner = f"worker_{index + 1:02d}"
        workers[candidate_id] = _initial_worker_entry(candidate_id, plan_name, hypothesis, owner)
        worker_ownership[candidate_id] = owner
        active_candidates.append(candidate_id)
        worker_actions[candidate_id] = [
            str(candidate.get("implementationSpec", "Build the first working version and measure it.")).strip()
        ]

        candidate_dir = impl_dir / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        for round_index in range(1, rounds + 1):
            (candidate_dir / f"round_{round_index}").mkdir(parents=True, exist_ok=True)

    shutil.copyfile(candidates_file, plan_dir / "candidates.json")
    if acceptance_file is not None:
        shutil.copyfile(acceptance_file, plan_dir / "acceptance_spec.json")

    board = {
        "run_id": run_id,
        "problem": problem,
        "acceptance_spec_path": "plan/acceptance_spec.json" if acceptance_file is not None else "",
        "round_index": 0,
        "workers": workers,
        "worker_ownership": worker_ownership,
        "peer_feedback": {},
        "global_findings": {
            "dominant_strengths": [],
            "dominant_failures": [],
            "candidate_rank_hint": [],
            "fusion_opportunities": [],
            "improvement_targets": [],
        },
    }
    agenda = {
        "round_index": 1,
        "ready_for_review": False,
        "active_candidates": active_candidates,
        "priority_questions": [
            "Which candidate has the strongest first measurable signal?",
            "Which implementation risk should be reduced before review?",
        ],
        "worker_actions": worker_actions,
    }

    save_json(shared_dir / "worker_board.json", board)
    save_json(shared_dir / "agenda.json", agenda)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a dynamic research run directory.")
    parser.add_argument("--root", required=True, help="Root directory that stores research runs.")
    parser.add_argument("--run-id", required=True, help="Unique run identifier.")
    parser.add_argument("--problem", required=True, help="Problem statement for the run.")
    parser.add_argument("--candidates-file", required=True, help="Path to candidates.json.")
    parser.add_argument("--acceptance-file", help="Path to acceptance_spec.json.")
    parser.add_argument("--rounds", type=int, default=3, help="Number of pre-created implementation rounds.")
    args = parser.parse_args()

    init_research_run(
        root=Path(args.root),
        run_id=args.run_id,
        problem=args.problem,
        candidates_file=Path(args.candidates_file),
        acceptance_file=Path(args.acceptance_file) if args.acceptance_file else None,
        rounds=args.rounds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
