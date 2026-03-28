from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import sys

BLACKBOARD_DIR = Path(__file__).resolve().parents[2] / "research-blackboard" / "scripts"
DIGEST_DIR = Path(__file__).resolve().parents[2] / "research-report-digest" / "scripts"
PLANNER_DIR = Path(__file__).resolve().parents[2] / "research-planner" / "scripts"
REVIEWER_DIR = Path(__file__).resolve().parents[2] / "research-reviewer" / "scripts"

for directory in (BLACKBOARD_DIR, DIGEST_DIR, PLANNER_DIR, REVIEWER_DIR):
    dir_str = str(directory)
    if dir_str not in sys.path:
        sys.path.insert(0, dir_str)

from add_peer_feedback import add_peer_feedback
from digest_report import digest_report
from finalize_conclusion import finalize_conclusion
from generate_agenda import generate_agenda
from generate_plan_bundle import generate_plan_bundle
from init_research_run import init_research_run
from research_board_lib import ensure_board_shape, load_json, normalize_lines, save_json
from review_run import review_run
from synthesize_findings import synthesize_findings
from upsert_worker_entry import upsert_worker_entry
from validate_board import validate_board


def _active_candidates(board: dict[str, Any]) -> list[str]:
    output: list[str] = []
    for cid, entry in board.get("workers", {}).items():
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "active")).strip().lower()
        if status not in {"dropped", "archived", "failed"}:
            output.append(cid)
    return output


def _resolve_artifacts(
    run_dir: Path,
    reports_root: Path | None,
    candidate_id: str,
    round_index: int,
    allow_fallback_rounds: bool,
) -> tuple[Path, Path, int, bool]:
    local_report = run_dir / "implementation" / candidate_id / f"round_{round_index}" / "report.md"
    local_metrics = run_dir / "implementation" / candidate_id / f"round_{round_index}" / "metrics.json"
    if local_report.exists() and local_metrics.exists():
        return local_report, local_metrics, round_index, False

    if reports_root is not None:
        ext_report = reports_root / f"{candidate_id}_round_{round_index}_report.md"
        ext_metrics = reports_root / f"{candidate_id}_round_{round_index}_metrics.json"
        if ext_report.exists() and ext_metrics.exists():
            return ext_report, ext_metrics, round_index, False

    if not allow_fallback_rounds:
        raise FileNotFoundError(
            f"Missing report/metrics for {candidate_id} round {round_index}. "
            "Provide files or enable fallback rounds."
        )

    candidates: list[tuple[int, Path, Path]] = []
    base = run_dir / "implementation" / candidate_id
    for report in base.glob("round_*/report.md"):
        round_name = report.parent.name
        if not round_name.startswith("round_"):
            continue
        try:
            idx = int(round_name.split("_", 1)[1])
        except ValueError:
            continue
        metrics = report.parent / "metrics.json"
        if metrics.exists():
            candidates.append((idx, report, metrics))

    if reports_root is not None:
        for report in reports_root.glob(f"{candidate_id}_round_*_report.md"):
            stem = report.stem
            try:
                idx = int(stem.split("_round_", 1)[1].split("_", 1)[0])
            except (IndexError, ValueError):
                continue
            metrics = reports_root / f"{candidate_id}_round_{idx}_metrics.json"
            if metrics.exists():
                candidates.append((idx, report, metrics))

    if not candidates:
        raise FileNotFoundError(
            f"No report/metrics pair found for {candidate_id}."
        )

    idx, report, metrics = sorted(candidates, key=lambda row: row[0])[-1]
    return report, metrics, idx, True


def _build_feedback(target_entry: dict[str, Any]) -> dict[str, list[str]]:
    strengths = normalize_lines(target_entry.get("strengths"))
    weaknesses = normalize_lines(target_entry.get("weaknesses"))
    open_problems = normalize_lines(target_entry.get("open_problems"))
    insights = normalize_lines(target_entry.get("transferable_insights"))
    next_moves = normalize_lines(target_entry.get("proposed_next_move"))

    observed_weaknesses = (weaknesses + open_problems)[:3]
    borrowable_ideas = insights[:3]

    suggested: list[str] = []
    for item in observed_weaknesses[:2]:
        suggested.append(f"Address weakness: {item}")
    for item in borrowable_ideas[:2]:
        suggested.append(f"Adopt insight: {item}")
    if not suggested and next_moves:
        suggested.extend(next_moves[:2])
    if not suggested:
        suggested.append("Run one focused improvement on the top risk in this candidate")

    return {
        "observed_strengths": strengths[:3],
        "observed_weaknesses": observed_weaknesses,
        "borrowable_ideas": borrowable_ideas,
        "suggested_improvement": suggested[:3],
    }


def run_round(
    run_dir: Path,
    round_index: int,
    reports_root: Path | None,
    max_rounds: int,
    review_feedback_path: Path | None,
    allow_fallback_rounds: bool,
) -> dict[str, Any]:
    board_path = run_dir / "shared" / "worker_board.json"
    agenda_path = run_dir / "shared" / "agenda.json"
    board = ensure_board_shape(load_json(board_path))
    active = _active_candidates(board)

    fallback_notes: list[str] = []

    for pos, candidate_id in enumerate(active, start=1):
        entry = board["workers"].get(candidate_id, {})
        plan_name = str(entry.get("plan_name", candidate_id)).strip() or candidate_id
        owner = str(entry.get("owner", f"worker_{pos:02d}")).strip() or f"worker_{pos:02d}"

        report_path, metrics_path, used_round, used_fallback = _resolve_artifacts(
            run_dir=run_dir,
            reports_root=reports_root,
            candidate_id=candidate_id,
            round_index=round_index,
            allow_fallback_rounds=allow_fallback_rounds,
        )
        if used_fallback:
            fallback_notes.append(
                f"{candidate_id}: requested round {round_index}, fallback to round {used_round}"
            )

        digest_path = run_dir / "shared" / f"{candidate_id}_round_{round_index}_digest.json"
        digest_report(
            report_path=report_path,
            metrics_path=metrics_path,
            candidate_id=candidate_id,
            plan_name=plan_name,
            round_index=used_round,
            owner=owner,
            output_path=digest_path,
            status="active",
        )
        upsert_worker_entry(board_path, candidate_id, digest_path)

    board = ensure_board_shape(load_json(board_path))
    active = _active_candidates(board)

    for from_candidate in active:
        for to_candidate in active:
            if from_candidate == to_candidate:
                continue
            target = board["workers"].get(to_candidate, {})
            feedback = _build_feedback(target)
            feedback_path = (
                run_dir
                / "shared"
                / "peer_feedback"
                / f"{from_candidate}_on_{to_candidate}_round_{round_index}.json"
            )
            save_json(feedback_path, feedback)
            add_peer_feedback(board_path, from_candidate, to_candidate, feedback_path)

    validate_board(board_path)
    synthesize_findings(board_path)
    agenda = generate_agenda(
        board_path=board_path,
        agenda_path=agenda_path,
        review_feedback_path=review_feedback_path,
        max_rounds=max_rounds,
    )

    return {
        "round": round_index,
        "active_candidates": active,
        "fallback_notes": fallback_notes,
        "agenda_round_index": agenda.get("round_index"),
    }


def run_full_cycle(
    run_root: Path,
    run_id: str,
    problem: str,
    candidate_count: int,
    max_rounds: int,
    max_review_cycles: int,
    reports_root: Path | None,
    allow_fallback_rounds: bool,
    auto_plan: bool,
    candidates_file_input: Path | None,
    acceptance_file_input: Path | None,
) -> dict[str, Any]:
    run_dir = run_root / run_id
    plan_dir = run_dir / "plan"
    candidates_file = plan_dir / "candidates.json"
    acceptance_file = plan_dir / "acceptance_spec.json"
    init_candidates_source = candidates_file
    init_acceptance_source = acceptance_file

    board_path = run_dir / "shared" / "worker_board.json"
    agenda_path = run_dir / "shared" / "agenda.json"

    if not candidates_file.exists() or not acceptance_file.exists():
        if candidates_file_input is not None and acceptance_file_input is not None:
            if not candidates_file_input.exists():
                raise FileNotFoundError(f"candidates file does not exist: {candidates_file_input}")
            if not acceptance_file_input.exists():
                raise FileNotFoundError(f"acceptance file does not exist: {acceptance_file_input}")
            plan_dir.mkdir(parents=True, exist_ok=True)
            if candidates_file_input.resolve() != candidates_file.resolve():
                shutil.copyfile(candidates_file_input, candidates_file)
            if acceptance_file_input.resolve() != acceptance_file.resolve():
                shutil.copyfile(acceptance_file_input, acceptance_file)
            init_candidates_source = candidates_file_input
            init_acceptance_source = acceptance_file_input
        elif auto_plan:
            generate_plan_bundle(
                problem=problem,
                output_dir=run_dir,
                candidate_count=candidate_count,
                search_results=8,
            )
        else:
            raise FileNotFoundError(
                "Plan files are missing. Provide --candidates-file/--acceptance-file or enable auto-plan."
            )

    if not board_path.exists() or not agenda_path.exists():
        init_research_run(
            root=run_root,
            run_id=run_id,
            problem=problem,
            candidates_file=init_candidates_source,
            acceptance_file=init_acceptance_source,
            rounds=max_rounds,
        )

    round_summaries: list[dict[str, Any]] = []
    review_feedback_path = run_dir / "review" / "review_feedback.json"
    review_report_path = run_dir / "review" / "review_report.md"

    for round_index in range(1, max_rounds + 1):
        summary = run_round(
            run_dir=run_dir,
            round_index=round_index,
            reports_root=reports_root,
            max_rounds=max_rounds,
            review_feedback_path=None,
            allow_fallback_rounds=allow_fallback_rounds,
        )
        round_summaries.append(summary)

    review_payload = review_run(
        board_path=board_path,
        agenda_path=agenda_path,
        acceptance_path=acceptance_file,
        output_feedback=review_feedback_path,
        output_report=review_report_path,
    )

    review_cycles = 1
    while not review_payload.get("approved", False) and review_cycles < max_review_cycles:
        agenda = generate_agenda(
            board_path=board_path,
            agenda_path=agenda_path,
            review_feedback_path=review_feedback_path,
            max_rounds=max_rounds,
        )
        target_round = int(agenda.get("round_index", max_rounds + review_cycles) or (max_rounds + review_cycles))

        try:
            summary = run_round(
                run_dir=run_dir,
                round_index=target_round,
                reports_root=reports_root,
                max_rounds=max(target_round, max_rounds),
                review_feedback_path=review_feedback_path,
                allow_fallback_rounds=allow_fallback_rounds,
            )
            round_summaries.append(summary)
        except FileNotFoundError:
            break

        review_payload = review_run(
            board_path=board_path,
            agenda_path=agenda_path,
            acceptance_path=acceptance_file,
            output_feedback=review_feedback_path,
            output_report=review_report_path,
        )
        review_cycles += 1

    conclusion_json = run_dir / "deliverables" / "final_conclusion.json"
    conclusion_md = run_dir / "deliverables" / "final_conclusion.md"
    conclusion = finalize_conclusion(
        board_path=board_path,
        agenda_path=agenda_path,
        output_json=conclusion_json,
        output_md=conclusion_md,
        review_feedback_path=review_feedback_path if review_feedback_path.exists() else None,
    )

    summary = {
        "run_dir": str(run_dir),
        "round_summaries": round_summaries,
        "review_cycles": review_cycles,
        "approved": bool(review_payload.get("approved", False)),
        "review_feedback_path": str(review_feedback_path),
        "review_report_path": str(review_report_path),
        "final_conclusion_json": str(conclusion_json),
        "final_conclusion_md": str(conclusion_md),
        "winner_candidate": conclusion.get("selected_solution", {}).get("winner_candidate_id", ""),
    }
    save_json(run_dir / "deliverables" / "pipeline_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run planner->implementer->reviewer full protocol cycle.")
    parser.add_argument("--run-root", required=True, help="Root directory containing research runs.")
    parser.add_argument("--run-id", required=True, help="Run id.")
    parser.add_argument("--problem", required=True, help="Problem statement.")
    parser.add_argument("--candidate-count", type=int, default=3, help="Planner candidate count (3-5).")
    parser.add_argument("--max-rounds", type=int, default=3, help="Default implementation rounds.")
    parser.add_argument("--max-review-cycles", type=int, default=2, help="Max reviewer gate cycles.")
    parser.add_argument("--reports-root", help="Optional reports dir with <candidate>_round_<n>_report.md files.")
    parser.add_argument("--candidates-file", help="Optional path to candidates.json used when run plan is missing.")
    parser.add_argument("--acceptance-file", help="Optional path to acceptance_spec.json used when run plan is missing.")
    parser.add_argument(
        "--strict-round-artifacts",
        action="store_true",
        help="Require exact round artifacts; disable fallback to latest available round.",
    )
    parser.add_argument(
        "--skip-auto-plan",
        action="store_true",
        help="Do not auto-generate plan files when missing.",
    )
    args = parser.parse_args()

    summary = run_full_cycle(
        run_root=Path(args.run_root),
        run_id=args.run_id,
        problem=args.problem,
        candidate_count=args.candidate_count,
        max_rounds=args.max_rounds,
        max_review_cycles=args.max_review_cycles,
        reports_root=Path(args.reports_root) if args.reports_root else None,
        allow_fallback_rounds=not args.strict_round_artifacts,
        auto_plan=not args.skip_auto_plan,
        candidates_file_input=Path(args.candidates_file) if args.candidates_file else None,
        acceptance_file_input=Path(args.acceptance_file) if args.acceptance_file else None,
    )
    save_json(Path(args.run_root) / args.run_id / "deliverables" / "run_full_cycle_stdout.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
