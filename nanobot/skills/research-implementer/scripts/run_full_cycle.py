from __future__ import annotations

import argparse
import concurrent.futures
import subprocess
import shutil
from pathlib import Path
from typing import Any

import sys

BLACKBOARD_DIR = Path(__file__).resolve().parents[2] / "research-blackboard" / "scripts"
DIGEST_DIR = Path(__file__).resolve().parents[2] / "research-report-digest" / "scripts"
PLANNER_DIR = Path(__file__).resolve().parents[2] / "research-planner" / "scripts"
REVIEWER_DIR = Path(__file__).resolve().parents[2] / "research-reviewer" / "scripts"
WORKER_DIR = Path(__file__).resolve().parents[2] / "research-worker" / "scripts"

for directory in (BLACKBOARD_DIR, DIGEST_DIR, PLANNER_DIR, REVIEWER_DIR):
    dir_str = str(directory)
    if dir_str not in sys.path:
        sys.path.insert(0, dir_str)

from add_peer_feedback import add_peer_feedback
from finalize_conclusion import finalize_conclusion
from generate_agenda import generate_agenda
from generate_plan_bundle import generate_plan_bundle
from init_research_run import init_research_run
from research_board_lib import ensure_board_shape, load_json, save_json
from review_run import review_run
from synthesize_findings import synthesize_findings
from upsert_worker_entry import upsert_worker_entry
from validate_board import validate_board
from debug_trace import DebugTrace


def _active_candidates(board: dict[str, Any]) -> list[str]:
    output: list[str] = []
    for cid, entry in board.get("workers", {}).items():
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "active")).strip().lower()
        if status not in {"dropped", "archived", "failed"}:
            output.append(cid)
    return output


def _run_subprocess(
    cmd: list[str],
    step: str,
    tracer: DebugTrace | None,
) -> tuple[bool, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        if tracer is not None:
            tracer.log(
                step=step,
                status="ok",
                message="subprocess finished",
                details={"cmd": cmd},
            )
        return True, ""
    note = (
        f"subprocess failed: {' '.join(cmd)}\n"
        f"stdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}\n"
    )
    if tracer is not None:
        tracer.log(
            step=step,
            status="error",
            message="subprocess failed",
            details={"cmd": cmd, "exit_code": proc.returncode},
        )
    return False, note


def run_round(
    run_dir: Path,
    round_index: int,
    reports_root: Path | None,
    max_rounds: int,
    review_feedback_path: Path | None,
    allow_fallback_rounds: bool,
    tracer: DebugTrace | None = None,
) -> dict[str, Any]:
    board_path = run_dir / "shared" / "worker_board.json"
    agenda_path = run_dir / "shared" / "agenda.json"
    board = ensure_board_shape(load_json(board_path))
    active = _active_candidates(board)
    if tracer is not None:
        tracer.log(
            step=f"round.{round_index}.start",
            status="start",
            message="start round execution",
            details={"active_candidates": active},
        )

    fallback_notes: list[str] = []
    worker_jobs: list[tuple[str, str, Path, list[str]]] = []
    pending_worker_dir = run_dir / "shared" / "pending_worker_round" / f"round_{round_index}"
    for pos, candidate_id in enumerate(active, start=1):
        entry = board["workers"].get(candidate_id, {})
        owner = str(entry.get("owner", f"worker_{pos:02d}")).strip() or f"worker_{pos:02d}"
        summary_path = pending_worker_dir / f"{candidate_id}.json"
        cmd = [
            sys.executable,
            str(WORKER_DIR / "run_worker_round.py"),
            "--run-dir",
            str(run_dir),
            "--candidate-id",
            candidate_id,
            "--round",
            str(round_index),
            "--owner",
            owner,
            "--summary-out",
            str(summary_path),
        ]
        if reports_root is not None:
            cmd.extend(["--reports-root", str(reports_root)])
        if allow_fallback_rounds:
            cmd.append("--allow-fallback-rounds")

        worker_jobs.append((candidate_id, owner, summary_path, cmd))
        if tracer is not None:
            tracer.log(
                step=f"round.{round_index}.candidate.{candidate_id}.spawn_worker",
                status="start",
                message="spawn worker subprocess",
                details={"owner": owner},
            )

    worker_errors: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(len(worker_jobs), 8))) as executor:
        future_map = {
            executor.submit(
                _run_subprocess,
                cmd,
                f"round.{round_index}.candidate.{candidate_id}.spawn_worker",
                tracer,
            ): (candidate_id, owner, summary_path)
            for candidate_id, owner, summary_path, cmd in worker_jobs
        }
        for future in concurrent.futures.as_completed(future_map):
            candidate_id, owner, summary_path = future_map[future]
            ok, note = future.result()
            if not ok:
                worker_errors.append(f"[{candidate_id}/{owner}] {note}")
            elif not summary_path.exists():
                worker_errors.append(f"[{candidate_id}/{owner}] summary file missing: {summary_path}")

    if worker_errors:
        raise RuntimeError("Worker subprocess round failed:\n" + "\n".join(worker_errors))

    for candidate_id, _, summary_path, _ in worker_jobs:
        summary = load_json(summary_path)
        owner = str(summary.get("owner", "")).strip()
        digest_path = Path(summary["digest_path"])
        upsert_worker_entry(board_path, candidate_id, digest_path, actor=owner)
        fallback_note = str(summary.get("fallback_note", "")).strip()
        if fallback_note:
            fallback_notes.append(fallback_note)
        if tracer is not None:
            tracer.log(
                step=f"round.{round_index}.candidate.{candidate_id}.digest",
                status="ok",
                message="worker digest merged into board",
                details={"digest_path": str(digest_path), "owner": owner},
            )

    board = ensure_board_shape(load_json(board_path))
    active = _active_candidates(board)
    feedback_jobs: list[tuple[str, str, Path, list[str]]] = []
    pending_feedback_dir = run_dir / "shared" / "pending_feedback_round" / f"round_{round_index}"
    for pos, from_candidate in enumerate(active, start=1):
        from_entry = board["workers"].get(from_candidate, {})
        owner = str(from_entry.get("owner", f"worker_{pos:02d}")).strip() or f"worker_{pos:02d}"
        summary_path = pending_feedback_dir / f"{from_candidate}.json"
        cmd = [
            sys.executable,
            str(WORKER_DIR / "run_peer_feedback.py"),
            "--run-dir",
            str(run_dir),
            "--from-candidate",
            from_candidate,
            "--round",
            str(round_index),
            "--summary-out",
            str(summary_path),
        ]
        feedback_jobs.append((from_candidate, owner, summary_path, cmd))

    feedback_errors: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(len(feedback_jobs), 8))) as executor:
        future_map = {
            executor.submit(
                _run_subprocess,
                cmd,
                f"round.{round_index}.candidate.{from_candidate}.peer_feedback",
                tracer,
            ): (from_candidate, owner, summary_path)
            for from_candidate, owner, summary_path, cmd in feedback_jobs
        }
        for future in concurrent.futures.as_completed(future_map):
            from_candidate, owner, summary_path = future_map[future]
            ok, note = future.result()
            if not ok:
                feedback_errors.append(f"[{from_candidate}/{owner}] {note}")
            elif not summary_path.exists():
                feedback_errors.append(f"[{from_candidate}/{owner}] summary file missing: {summary_path}")

    if feedback_errors:
        raise RuntimeError("Peer feedback subprocess round failed:\n" + "\n".join(feedback_errors))

    feedback_count = 0
    for from_candidate, _, summary_path, _ in feedback_jobs:
        summary = load_json(summary_path)
        actor = str(summary.get("owner", "")).strip()
        for row in summary.get("feedback_files", []):
            if not isinstance(row, dict):
                continue
            to_candidate = str(row.get("to_candidate", "")).strip()
            feedback_path_text = str(row.get("feedback_path", "")).strip()
            if not to_candidate or not feedback_path_text:
                continue
            feedback_path = Path(feedback_path_text)
            add_peer_feedback(
                board_path=board_path,
                from_candidate=from_candidate,
                to_candidate=to_candidate,
                feedback_path=feedback_path,
                actor=actor,
            )
            feedback_count += 1

    if tracer is not None:
        tracer.log(
            step=f"round.{round_index}.peer_feedback",
            status="ok",
            message="peer feedback merged",
            details={"feedback_entries": feedback_count},
        )

    validate_board(board_path)
    if tracer is not None:
        tracer.log(
            step=f"round.{round_index}.validate_board",
            status="ok",
            message="worker board validated",
            details={"board_path": str(board_path)},
        )
    synthesize_findings(board_path)
    if tracer is not None:
        tracer.log(
            step=f"round.{round_index}.synthesize_findings",
            status="ok",
            message="global findings updated",
            details={},
        )
    agenda = generate_agenda(
        board_path=board_path,
        agenda_path=agenda_path,
        review_feedback_path=review_feedback_path,
        max_rounds=max_rounds,
    )
    if tracer is not None:
        tracer.log(
            step=f"round.{round_index}.generate_agenda",
            status="ok",
            message="agenda generated",
            details={"agenda_round_index": agenda.get("round_index")},
        )

    summary = {
        "round": round_index,
        "active_candidates": active,
        "fallback_notes": fallback_notes,
        "agenda_round_index": agenda.get("round_index"),
    }
    if tracer is not None:
        tracer.log(
            step=f"round.{round_index}.finish",
            status="ok",
            message="round finished",
            details=summary,
        )
    return summary


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
    debug_enabled: bool = True,
    debug_console: bool = False,
) -> dict[str, Any]:
    run_dir = run_root / run_id
    tracer = DebugTrace(run_dir=run_dir, enabled=debug_enabled, console=debug_console)
    tracer.log(
        step="pipeline.start",
        status="start",
        message="run_full_cycle started",
        details={
            "run_id": run_id,
            "run_root": str(run_root),
            "problem": problem,
            "max_rounds": max_rounds,
            "max_review_cycles": max_review_cycles,
            "auto_plan": auto_plan,
            "allow_fallback_rounds": allow_fallback_rounds,
        },
    )

    plan_dir = run_dir / "plan"
    candidates_file = plan_dir / "candidates.json"
    acceptance_file = plan_dir / "acceptance_spec.json"
    init_candidates_source = candidates_file
    init_acceptance_source = acceptance_file

    board_path = run_dir / "shared" / "worker_board.json"
    agenda_path = run_dir / "shared" / "agenda.json"

    if not candidates_file.exists() or not acceptance_file.exists():
        tracer.log(
            step="pipeline.plan.prepare",
            status="start",
            message="plan files missing; preparing plan artifacts",
            details={
                "candidates_exists": candidates_file.exists(),
                "acceptance_exists": acceptance_file.exists(),
            },
        )
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
            tracer.log(
                step="pipeline.plan.prepare",
                status="ok",
                message="plan files copied from provided inputs",
                details={
                    "candidates_file": str(candidates_file),
                    "acceptance_file": str(acceptance_file),
                },
            )
        elif auto_plan:
            generate_plan_bundle(
                problem=problem,
                output_dir=run_dir,
                candidate_count=candidate_count,
                search_results=8,
            )
            tracer.log(
                step="pipeline.plan.prepare",
                status="ok",
                message="plan bundle auto-generated",
                details={
                    "candidate_count": candidate_count,
                    "plan_dir": str(plan_dir),
                },
            )
        else:
            tracer.log(
                step="pipeline.plan.prepare",
                status="error",
                message="plan files missing and auto-plan disabled",
                details={},
            )
            raise FileNotFoundError(
                "Plan files are missing. Provide --candidates-file/--acceptance-file or enable auto-plan."
            )

    if not board_path.exists() or not agenda_path.exists():
        tracer.log(
            step="pipeline.init_run",
            status="start",
            message="initializing run directory and shared artifacts",
            details={},
        )
        init_research_run(
            root=run_root,
            run_id=run_id,
            problem=problem,
            candidates_file=init_candidates_source,
            acceptance_file=init_acceptance_source,
            rounds=max_rounds,
        )
        tracer.log(
            step="pipeline.init_run",
            status="ok",
            message="run initialized",
            details={"board_path": str(board_path), "agenda_path": str(agenda_path)},
        )

    round_summaries: list[dict[str, Any]] = []
    review_feedback_path = run_dir / "review" / "review_feedback.json"
    review_report_path = run_dir / "review" / "review_report.md"

    for round_index in range(1, max_rounds + 1):
        tracer.log(
            step=f"pipeline.round_loop.{round_index}",
            status="start",
            message="run default round",
            details={},
        )
        summary = run_round(
            run_dir=run_dir,
            round_index=round_index,
            reports_root=reports_root,
            max_rounds=max_rounds,
            review_feedback_path=None,
            allow_fallback_rounds=allow_fallback_rounds,
            tracer=tracer,
        )
        round_summaries.append(summary)

    tracer.log(
        step="pipeline.review.initial",
        status="start",
        message="run initial review",
        details={},
    )
    review_payload = review_run(
        board_path=board_path,
        agenda_path=agenda_path,
        acceptance_path=acceptance_file,
        output_feedback=review_feedback_path,
        output_report=review_report_path,
    )
    tracer.log(
        step="pipeline.review.initial",
        status="ok",
        message="initial review completed",
        details={"approved": bool(review_payload.get("approved", False))},
    )

    review_cycles = 1
    while not review_payload.get("approved", False) and review_cycles < max_review_cycles:
        tracer.log(
            step=f"pipeline.review_cycle.{review_cycles + 1}",
            status="start",
            message="review rejected; generating recovery agenda",
            details={},
        )
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
                tracer=tracer,
            )
            round_summaries.append(summary)
        except FileNotFoundError:
            tracer.log(
                step=f"pipeline.review_cycle.{review_cycles + 1}",
                status="warn",
                message="stop recovery loop due to missing artifacts",
                details={"target_round": target_round},
            )
            break

        review_payload = review_run(
            board_path=board_path,
            agenda_path=agenda_path,
            acceptance_path=acceptance_file,
            output_feedback=review_feedback_path,
            output_report=review_report_path,
        )
        tracer.log(
            step=f"pipeline.review_cycle.{review_cycles + 1}",
            status="ok",
            message="review cycle completed",
            details={"approved": bool(review_payload.get("approved", False))},
        )
        review_cycles += 1

    tracer.log(
        step="pipeline.finalize",
        status="start",
        message="building final conclusion artifacts",
        details={},
    )
    conclusion_json = run_dir / "deliverables" / "final_conclusion.json"
    conclusion_md = run_dir / "deliverables" / "final_conclusion.md"
    conclusion = finalize_conclusion(
        board_path=board_path,
        agenda_path=agenda_path,
        output_json=conclusion_json,
        output_md=conclusion_md,
        review_feedback_path=review_feedback_path if review_feedback_path.exists() else None,
    )
    tracer.log(
        step="pipeline.finalize",
        status="ok",
        message="final conclusion generated",
        details={
            "winner_candidate": conclusion.get("selected_solution", {}).get("winner_candidate_id", ""),
            "review_status": conclusion.get("readiness", {}).get("review_status", ""),
        },
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
        "debug_trace_jsonl": tracer.paths()["jsonl"],
        "debug_trace_markdown": tracer.paths()["markdown"],
    }
    save_json(run_dir / "deliverables" / "pipeline_summary.json", summary)
    tracer.log(
        step="pipeline.finish",
        status="ok",
        message="run_full_cycle finished",
        details={"approved": summary["approved"], "review_cycles": summary["review_cycles"]},
    )
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
        "--allow-fallback-round-artifacts",
        action="store_true",
        help="Allow fallback to latest available round artifacts when exact round files are missing.",
    )
    parser.add_argument(
        "--skip-auto-plan",
        action="store_true",
        help="Do not auto-generate plan files when missing.",
    )
    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="Disable runtime debug trace file generation.",
    )
    parser.add_argument(
        "--debug-console",
        action="store_true",
        help="Print debug events to console while writing trace files.",
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
        allow_fallback_rounds=args.allow_fallback_round_artifacts,
        auto_plan=not args.skip_auto_plan,
        candidates_file_input=Path(args.candidates_file) if args.candidates_file else None,
        acceptance_file_input=Path(args.acceptance_file) if args.acceptance_file else None,
        debug_enabled=not args.no_debug,
        debug_console=args.debug_console,
    )
    save_json(Path(args.run_root) / args.run_id / "deliverables" / "run_full_cycle_stdout.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
