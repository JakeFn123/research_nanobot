from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import sys

SKILLS_DIR = Path(__file__).resolve().parents[2]
PLANNER_DIR = SKILLS_DIR / "research-planner" / "scripts"
DIGEST_DIR = SKILLS_DIR / "research-report-digest" / "scripts"
WORKER_DIR = SKILLS_DIR / "research-worker" / "scripts"
BLACKBOARD_DIR = SKILLS_DIR / "research-blackboard" / "scripts"
REVIEWER_DIR = SKILLS_DIR / "research-reviewer" / "scripts"

for directory in (PLANNER_DIR, DIGEST_DIR, WORKER_DIR, BLACKBOARD_DIR, REVIEWER_DIR):
    dir_str = str(directory)
    if dir_str not in sys.path:
        sys.path.insert(0, dir_str)

from debug_trace import DebugTrace
from digest_report import digest_report
from generate_plan_bundle import generate_plan_bundle
from inbox_lib import send_message
from research_board_lib import extract_candidates, load_json, normalize_lines, save_json
from review_inbox_run import review_inbox_run
from route_review_feedback import route_review_feedback
from summarize_round_messages import summarize_round_messages
from worker_round_lib import build_feedback_from_entry, resolve_artifacts


def _candidate_rows(candidates_payload: Any) -> list[dict[str, Any]]:
    rows = extract_candidates(candidates_payload)
    out: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        candidate_id = str(row.get("candidateId") or row.get("candidate_id") or "").strip()
        if not candidate_id:
            candidate_id = f"candidate_{index:02d}"
        plan_name = str(row.get("name") or row.get("title") or row.get("planName") or candidate_id).strip() or candidate_id
        out.append({"candidate_id": candidate_id, "plan_name": plan_name, "worker": f"worker_{index:02d}"})
    return out


def _prepare_plan(
    *,
    run_dir: Path,
    problem: str,
    candidate_count: int,
    auto_plan: bool,
    candidates_file_input: Path | None,
    acceptance_file_input: Path | None,
) -> tuple[Path, Path]:
    plan_dir = run_dir / "plan"
    candidates_file = plan_dir / "candidates.json"
    acceptance_file = plan_dir / "acceptance_spec.json"

    if candidates_file.exists() and acceptance_file.exists():
        return candidates_file, acceptance_file

    plan_dir.mkdir(parents=True, exist_ok=True)

    if candidates_file_input is not None and acceptance_file_input is not None:
        if not candidates_file_input.exists():
            raise FileNotFoundError(f"candidates file does not exist: {candidates_file_input}")
        if not acceptance_file_input.exists():
            raise FileNotFoundError(f"acceptance file does not exist: {acceptance_file_input}")
        if candidates_file_input.resolve() != candidates_file.resolve():
            shutil.copyfile(candidates_file_input, candidates_file)
        if acceptance_file_input.resolve() != acceptance_file.resolve():
            shutil.copyfile(acceptance_file_input, acceptance_file)
        return candidates_file, acceptance_file

    if auto_plan:
        generate_plan_bundle(
            problem=problem,
            output_dir=run_dir,
            candidate_count=candidate_count,
            search_results=8,
        )
        return candidates_file, acceptance_file

    raise FileNotFoundError("Plan files are missing. Provide candidates/acceptance files or enable auto-plan.")


def _peer_payload_from_digest(digest: dict[str, Any]) -> dict[str, list[str]]:
    entry = {
        "strengths": normalize_lines(digest.get("strengths")),
        "weaknesses": normalize_lines(digest.get("weaknesses")),
        "open_problems": normalize_lines(digest.get("open_problems")),
        "transferable_insights": normalize_lines(digest.get("transferable_insights")),
        "proposed_next_move": normalize_lines(digest.get("proposed_next_move")),
    }
    return build_feedback_from_entry(entry)


def _finalize_inbox_conclusion(
    *,
    run_dir: Path,
    round_summary_path: Path,
    review_feedback_path: Path,
    acceptance_path: Path,
    output_json: Path,
    output_md: Path,
    problem: str,
) -> dict[str, Any]:
    summary = load_json(round_summary_path)
    review = load_json(review_feedback_path)
    acceptance = load_json(acceptance_path)

    if not isinstance(summary, dict):
        raise ValueError("round summary must be JSON object")
    if not isinstance(review, dict):
        review = {"approved": None, "must_fix": [], "optional_improvements": [], "evidence": []}
    if not isinstance(acceptance, dict):
        acceptance = {"hard_requirements": [], "soft_requirements": [], "review_checks": []}

    ranks = summary.get("candidate_rank_hint", []) if isinstance(summary.get("candidate_rank_hint"), list) else []
    winner_candidate = ""
    if ranks and isinstance(ranks[0], dict):
        winner_candidate = str(ranks[0].get("candidate_id", "")).strip()

    candidate_summaries = summary.get("candidate_summaries", {}) if isinstance(summary.get("candidate_summaries"), dict) else {}
    winner_name = ""
    if winner_candidate and isinstance(candidate_summaries.get(winner_candidate), dict):
        winner_name = str(candidate_summaries[winner_candidate].get("plan_name", "")).strip()

    supporting = []
    for row in ranks[1:3]:
        if isinstance(row, dict):
            cid = str(row.get("candidate_id", "")).strip()
            if cid:
                supporting.append(cid)

    approved = review.get("approved")
    if approved is True:
        review_status = "approved"
        ready = True
    elif approved is False:
        review_status = "rejected"
        ready = False
    else:
        review_status = "pending_review"
        ready = False

    conclusion = {
        "run_id": run_dir.name,
        "problem": problem,
        "round_index": int(summary.get("round", 0) or 0),
        "readiness": {
            "review_status": review_status,
            "ready_for_delivery": ready,
        },
        "selected_solution": {
            "strategy": "fusion" if supporting else "single",
            "winner_candidate_id": winner_candidate,
            "winner_plan_name": winner_name,
            "supporting_candidates": supporting,
        },
        "evidence_summary": {
            "dominant_strengths": summary.get("dominant_strengths", []),
            "dominant_failures": summary.get("dominant_failures", []),
            "improvement_targets": summary.get("improvement_targets", []),
            "candidate_rank_hint": ranks,
        },
        "review_feedback": {
            "approved": review.get("approved"),
            "must_fix": normalize_lines(review.get("must_fix")),
            "optional_improvements": normalize_lines(review.get("optional_improvements")),
            "evidence": normalize_lines(review.get("evidence")),
        },
        "acceptance_summary": {
            "hard_requirements": normalize_lines(acceptance.get("hard_requirements")),
            "soft_requirements": normalize_lines(acceptance.get("soft_requirements")),
            "review_checks": acceptance.get("review_checks", []),
            "status": review_status if review_status in {"approved", "rejected"} else "pending_review",
        },
        "final_recommendation": (
            f"Deploy {winner_candidate or 'the top candidate'} as the final inbox baseline and monitor next iteration risks."
            if review_status == "approved"
            else "Do not finalize yet. Continue redo cycle on reviewer must-fix items."
        ),
        "next_actions": (
            [
                "Package final artifacts with inbox trace evidence.",
                "Run one regression pass before release.",
            ]
            if review_status == "approved"
            else normalize_lines(review.get("must_fix"))
            or ["Address reviewer must-fix items and rerun review."]
        ),
    }

    save_json(output_json, conclusion)

    lines = [
        "# Final Conclusion (Inbox Mode)",
        "",
        f"- run_id: {conclusion['run_id']}",
        f"- problem: {conclusion['problem']}",
        f"- review_status: {conclusion['readiness']['review_status']}",
        f"- ready_for_delivery: {str(conclusion['readiness']['ready_for_delivery']).lower()}",
        "",
        "## Selected Solution",
        "",
        f"- winner_candidate_id: {conclusion['selected_solution']['winner_candidate_id']}",
        f"- winner_plan_name: {conclusion['selected_solution']['winner_plan_name']}",
        f"- strategy: {conclusion['selected_solution']['strategy']}",
        "",
        "## Final Recommendation",
        "",
        conclusion["final_recommendation"],
        "",
        "## Next Actions",
        "",
    ]
    next_actions = conclusion.get("next_actions", [])
    if isinstance(next_actions, list) and next_actions:
        for item in next_actions:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return conclusion


def _trace_event(
    *,
    tracer: DebugTrace,
    step: str,
    status: str,
    message: str,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    artifacts: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    details: dict[str, Any] = {}
    details["inputs"] = inputs or {}
    details["outputs"] = outputs or {}
    details["artifacts"] = artifacts or []
    if extra:
        details["extra"] = extra
    tracer.log(step=step, status=status, message=message, details=details)


def run_inbox_cycle(
    *,
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
    inbox_root = run_dir / "runtime" / "inbox"
    tracer = DebugTrace(run_dir=run_dir, enabled=debug_enabled, console=debug_console)
    _trace_event(
        tracer=tracer,
        step="pipeline.inbox.start",
        status="start",
        message="run_inbox_cycle started",
        inputs={
            "run_id": run_id,
            "problem": problem,
            "candidate_count": candidate_count,
            "max_rounds": max_rounds,
            "max_review_cycles": max_review_cycles,
            "allow_fallback_rounds": allow_fallback_rounds,
            "auto_plan": auto_plan,
        },
        outputs={"run_dir": str(run_dir), "inbox_root": str(inbox_root)},
    )

    candidates_file, acceptance_file = _prepare_plan(
        run_dir=run_dir,
        problem=problem,
        candidate_count=candidate_count,
        auto_plan=auto_plan,
        candidates_file_input=candidates_file_input,
        acceptance_file_input=acceptance_file_input,
    )

    candidate_rows = _candidate_rows(load_json(candidates_file))
    if len(candidate_rows) < 3:
        raise ValueError("inbox cycle requires 3-5 candidates")
    candidate_rows = candidate_rows[:5]

    inbox_root.mkdir(parents=True, exist_ok=True)
    save_json(run_dir / "runtime" / "worker_registry.json", candidate_rows)

    # Planner handoff
    plan_bundle_msg = send_message(
        inbox_root=inbox_root,
        run_id=run_id,
        round_index=0,
        from_role="planner",
        to_role="implementer",
        message_type="plan_bundle_ready",
        correlation_id="plan_bundle",
        payload={
            "problem": problem,
            "candidate_count": len(candidate_rows),
            "candidates_file": str(candidates_file),
            "acceptance_file": str(acceptance_file),
        },
        artifacts=[str(candidates_file), str(acceptance_file)],
    )
    _trace_event(
        tracer=tracer,
        step="pipeline.inbox.plan_bundle",
        status="ok",
        message="planner handoff published",
        inputs={
            "candidate_rows": candidate_rows,
            "candidates_file": str(candidates_file),
            "acceptance_file": str(acceptance_file),
        },
        outputs={"message_id": plan_bundle_msg.get("id", "")},
        artifacts=[str(candidates_file), str(acceptance_file)],
    )

    round_summaries: list[dict[str, Any]] = []

    for round_index in range(1, max_rounds + 1):
        _trace_event(
            tracer=tracer,
            step=f"pipeline.inbox.round.{round_index}",
            status="start",
            message="start round",
            inputs={"round": round_index},
            outputs={"candidate_count": len(candidate_rows)},
        )
        digests_by_candidate: dict[str, dict[str, Any]] = {}

        for row in candidate_rows:
            candidate_id = row["candidate_id"]
            worker_role = row["worker"]
            plan_name = row["plan_name"]

            task_msg = send_message(
                inbox_root=inbox_root,
                run_id=run_id,
                round_index=round_index,
                from_role="implementer",
                to_role=worker_role,
                message_type="worker_task_assigned",
                correlation_id=f"task_{candidate_id}_r{round_index}",
                payload={"candidate_id": candidate_id, "plan_name": plan_name, "round": round_index},
            )

            report_path, metrics_path, used_round, used_fallback = resolve_artifacts(
                run_dir=run_dir,
                reports_root=reports_root,
                candidate_id=candidate_id,
                round_index=round_index,
                allow_fallback_rounds=allow_fallback_rounds,
            )

            digest_path = run_dir / "runtime" / "private_digests" / f"{candidate_id}_round_{round_index}_digest.json"
            digest = digest_report(
                report_path=report_path,
                metrics_path=metrics_path,
                candidate_id=candidate_id,
                plan_name=plan_name,
                round_index=used_round,
                owner=worker_role,
                output_path=digest_path,
                status="active",
            )

            payload = {
                "candidate_id": candidate_id,
                "owner": worker_role,
                "plan_name": plan_name,
                "round": round_index,
                "key_hypothesis": str(digest.get("key_hypothesis", "")).strip(),
                "core_metrics": digest.get("core_metrics", {}),
                "strengths": normalize_lines(digest.get("strengths")),
                "weaknesses": normalize_lines(digest.get("weaknesses")),
                "transferable_insights": normalize_lines(digest.get("transferable_insights")),
                "open_problems": normalize_lines(digest.get("open_problems")),
                "next_move": normalize_lines(digest.get("proposed_next_move")),
                "private_report_ref": str(report_path),
            }
            update_msg = send_message(
                inbox_root=inbox_root,
                run_id=run_id,
                round_index=round_index,
                from_role=worker_role,
                to_role="implementer",
                message_type="worker_round_update",
                correlation_id=f"update_{candidate_id}_r{round_index}",
                payload=payload,
                artifacts=[str(report_path), str(metrics_path)],
            )

            digests_by_candidate[candidate_id] = payload
            _trace_event(
                tracer=tracer,
                step=f"round.{round_index}.worker.{candidate_id}",
                status="ok",
                message="worker round update published",
                inputs={
                    "candidate_id": candidate_id,
                    "worker_role": worker_role,
                    "task_message_id": task_msg.get("id", ""),
                    "report_path": str(report_path),
                    "metrics_path": str(metrics_path),
                },
                outputs={
                    "digest_path": str(digest_path),
                    "update_message_id": update_msg.get("id", ""),
                    "used_round": used_round,
                    "fallback": used_fallback,
                },
                artifacts=[str(report_path), str(metrics_path), str(digest_path)],
            )

        # Peer key insight + improvement proposal exchange
        for from_row in candidate_rows:
            from_candidate = from_row["candidate_id"]
            from_worker = from_row["worker"]
            for to_row in candidate_rows:
                to_candidate = to_row["candidate_id"]
                to_worker = to_row["worker"]
                if from_candidate == to_candidate:
                    continue

                target_digest = digests_by_candidate.get(to_candidate, {})
                peer_payload = _peer_payload_from_digest(target_digest)

                send_message(
                    inbox_root=inbox_root,
                    run_id=run_id,
                    round_index=round_index,
                    from_role=from_worker,
                    to_role=to_worker,
                    message_type="peer_key_insight",
                    correlation_id=f"peer_{from_candidate}_to_{to_candidate}_r{round_index}",
                    payload={
                        "from_candidate": from_candidate,
                        "to_candidate": to_candidate,
                        **peer_payload,
                    },
                )

                send_message(
                    inbox_root=inbox_root,
                    run_id=run_id,
                    round_index=round_index,
                    from_role=from_worker,
                    to_role="implementer",
                    message_type="improvement_proposal",
                    correlation_id=f"improve_{from_candidate}_to_{to_candidate}_r{round_index}",
                    payload={
                        "from_candidate": from_candidate,
                        "to_candidate": to_candidate,
                        "suggested_improvement": peer_payload.get("suggested_improvement", []),
                        "borrowable_ideas": peer_payload.get("borrowable_ideas", []),
                    },
                )

        round_summary_path = run_dir / "runtime" / "round_summaries" / f"round_{round_index}.json"
        round_summary = summarize_round_messages(
            run_dir=run_dir,
            round_index=round_index,
            output_path=round_summary_path,
        )
        round_summaries.append(round_summary)

        synthesis_msg = send_message(
            inbox_root=inbox_root,
            run_id=run_id,
            round_index=round_index,
            from_role="implementer",
            to_role="reviewer",
            message_type="round_synthesis_ready",
            correlation_id=f"synthesis_r{round_index}",
            payload={
                "round": round_index,
                "round_summary": str(round_summary_path),
                "candidate_rank_hint": round_summary.get("candidate_rank_hint", []),
            },
            artifacts=[str(round_summary_path)],
        )
        _trace_event(
            tracer=tracer,
            step=f"round.{round_index}.synthesis",
            status="ok",
            message="round synthesis ready",
            inputs={
                "round": round_index,
                "worker_updates": len(digests_by_candidate),
            },
            outputs={
                "summary_path": str(round_summary_path),
                "reviewer_message_id": synthesis_msg.get("id", ""),
                "candidate_rank_hint": round_summary.get("candidate_rank_hint", []),
            },
            artifacts=[str(round_summary_path)],
        )

    review_feedback_path = run_dir / "review" / "review_feedback.json"
    review_report_path = run_dir / "review" / "review_report.md"

    review_request_msg = send_message(
        inbox_root=inbox_root,
        run_id=run_id,
        round_index=max_rounds,
        from_role="implementer",
        to_role="reviewer",
        message_type="review_request",
        correlation_id="review_initial",
        payload={
            "acceptance_path": str(acceptance_file),
            "latest_round_summary": str(run_dir / "runtime" / "round_summaries" / f"round_{max_rounds}.json"),
        },
    )

    review_payload = review_inbox_run(
        run_dir=run_dir,
        acceptance_path=acceptance_file,
        output_feedback=review_feedback_path,
        output_report=review_report_path,
    )

    review_result_msg = send_message(
        inbox_root=inbox_root,
        run_id=run_id,
        round_index=max_rounds,
        from_role="reviewer",
        to_role="implementer",
        message_type=("review_result_approved" if review_payload.get("approved", False) else "review_result_rejected"),
        correlation_id="review_initial_result",
        payload=review_payload,
        artifacts=[str(review_feedback_path), str(review_report_path)],
    )
    _trace_event(
        tracer=tracer,
        step="pipeline.inbox.review.initial",
        status="ok",
        message="initial review completed",
        inputs={
            "review_request_message_id": review_request_msg.get("id", ""),
            "acceptance_file": str(acceptance_file),
            "latest_round_summary": str(run_dir / "runtime" / "round_summaries" / f"round_{max_rounds}.json"),
        },
        outputs={
            "review_result_message_id": review_result_msg.get("id", ""),
            "approved": bool(review_payload.get("approved", False)),
            "must_fix_count": len(normalize_lines(review_payload.get("must_fix"))),
        },
        artifacts=[str(review_feedback_path), str(review_report_path)],
    )

    review_cycles = 1
    while not review_payload.get("approved", False) and review_cycles < max_review_cycles:
        redo_round = max_rounds + review_cycles
        _trace_event(
            tracer=tracer,
            step=f"pipeline.inbox.review.redo.{review_cycles + 1}",
            status="start",
            message="routing reviewer feedback",
            inputs={"redo_round": redo_round, "review_cycle": review_cycles + 1},
            outputs={},
        )

        routing_summary_path = run_dir / "review" / f"redo_routing_round_{redo_round}.json"
        route_review_feedback(
            run_dir=run_dir,
            review_feedback_path=review_feedback_path,
            round_index=redo_round,
            output_path=routing_summary_path,
        )

        # Redo round: rerun worker updates with latest available artifacts
        redo_blocked = False
        digests_by_candidate: dict[str, dict[str, Any]] = {}
        for row in candidate_rows:
            candidate_id = row["candidate_id"]
            worker_role = row["worker"]
            plan_name = row["plan_name"]

            try:
                report_path, metrics_path, used_round, used_fallback = resolve_artifacts(
                    run_dir=run_dir,
                    reports_root=reports_root,
                    candidate_id=candidate_id,
                    round_index=redo_round,
                    allow_fallback_rounds=allow_fallback_rounds,
                )
            except FileNotFoundError as exc:
                redo_blocked = True
                _trace_event(
                    tracer=tracer,
                    step=f"round.{redo_round}.worker.{candidate_id}",
                    status="warn",
                    message="redo worker update skipped: missing artifacts",
                    inputs={
                        "candidate_id": candidate_id,
                        "redo_round": redo_round,
                    },
                    outputs={
                        "error": str(exc),
                        "allow_fallback_rounds": allow_fallback_rounds,
                    },
                )
                break
            digest_path = run_dir / "runtime" / "private_digests" / f"{candidate_id}_round_{redo_round}_digest.json"
            digest = digest_report(
                report_path=report_path,
                metrics_path=metrics_path,
                candidate_id=candidate_id,
                plan_name=plan_name,
                round_index=used_round,
                owner=worker_role,
                output_path=digest_path,
                status="active",
            )
            payload = {
                "candidate_id": candidate_id,
                "owner": worker_role,
                "plan_name": plan_name,
                "round": redo_round,
                "key_hypothesis": str(digest.get("key_hypothesis", "")).strip(),
                "core_metrics": digest.get("core_metrics", {}),
                "strengths": normalize_lines(digest.get("strengths")),
                "weaknesses": normalize_lines(digest.get("weaknesses")),
                "transferable_insights": normalize_lines(digest.get("transferable_insights")),
                "open_problems": normalize_lines(digest.get("open_problems")),
                "next_move": normalize_lines(digest.get("proposed_next_move")),
                "private_report_ref": str(report_path),
            }
            redo_update_msg = send_message(
                inbox_root=inbox_root,
                run_id=run_id,
                round_index=redo_round,
                from_role=worker_role,
                to_role="implementer",
                message_type="worker_round_update",
                correlation_id=f"redo_update_{candidate_id}_r{redo_round}",
                payload=payload,
                artifacts=[str(report_path), str(metrics_path)],
            )
            digests_by_candidate[candidate_id] = payload
            _trace_event(
                tracer=tracer,
                step=f"round.{redo_round}.worker.{candidate_id}",
                status="ok",
                message="redo worker update published",
                inputs={
                    "candidate_id": candidate_id,
                    "report_path": str(report_path),
                    "metrics_path": str(metrics_path),
                },
                outputs={
                    "redo_update_message_id": redo_update_msg.get("id", ""),
                    "used_round": used_round,
                    "fallback": used_fallback,
                },
                artifacts=[str(report_path), str(metrics_path), str(digest_path)],
            )

        if redo_blocked:
            _trace_event(
                tracer=tracer,
                step=f"pipeline.inbox.review.redo.{review_cycles + 1}",
                status="warn",
                message="redo iteration stopped due to missing artifacts",
                inputs={"redo_round": redo_round},
                outputs={"blocked": True},
            )
            break

        round_summary_path = run_dir / "runtime" / "round_summaries" / f"round_{redo_round}.json"
        round_summary = summarize_round_messages(run_dir=run_dir, round_index=redo_round, output_path=round_summary_path)
        round_summaries.append(round_summary)

        review_payload = review_inbox_run(
            run_dir=run_dir,
            acceptance_path=acceptance_file,
            output_feedback=review_feedback_path,
            output_report=review_report_path,
        )
        redo_review_result_msg = send_message(
            inbox_root=inbox_root,
            run_id=run_id,
            round_index=redo_round,
            from_role="reviewer",
            to_role="implementer",
            message_type=("review_result_approved" if review_payload.get("approved", False) else "review_result_rejected"),
            correlation_id=f"review_redo_result_{redo_round}",
            payload=review_payload,
            artifacts=[str(review_feedback_path), str(review_report_path)],
        )
        review_cycles += 1
        _trace_event(
            tracer=tracer,
            step=f"pipeline.inbox.review.redo.{review_cycles}",
            status="ok",
            message="redo review completed",
            inputs={
                "redo_round": redo_round,
                "round_summary_path": str(round_summary_path),
            },
            outputs={
                "review_result_message_id": redo_review_result_msg.get("id", ""),
                "approved": bool(review_payload.get("approved", False)),
                "must_fix_count": len(normalize_lines(review_payload.get("must_fix"))),
            },
            artifacts=[str(round_summary_path), str(review_feedback_path), str(review_report_path)],
        )

    latest_round = max_rounds if not round_summaries else int(round_summaries[-1].get("round", max_rounds) or max_rounds)
    latest_round_summary_path = run_dir / "runtime" / "round_summaries" / f"round_{latest_round}.json"

    conclusion_json = run_dir / "deliverables" / "final_conclusion_inbox.json"
    conclusion_md = run_dir / "deliverables" / "final_conclusion_inbox.md"
    conclusion = _finalize_inbox_conclusion(
        run_dir=run_dir,
        round_summary_path=latest_round_summary_path,
        review_feedback_path=review_feedback_path,
        acceptance_path=acceptance_file,
        output_json=conclusion_json,
        output_md=conclusion_md,
        problem=problem,
    )

    final_package_msg = send_message(
        inbox_root=inbox_root,
        run_id=run_id,
        round_index=latest_round,
        from_role="implementer",
        to_role="planner",
        message_type="final_package_ready",
        correlation_id="final_package",
        payload={"winner_candidate": conclusion.get("selected_solution", {}).get("winner_candidate_id", "")},
        artifacts=[str(conclusion_json), str(conclusion_md)],
    )

    summary = {
        "run_dir": str(run_dir),
        "approved": bool(review_payload.get("approved", False)),
        "review_cycles": review_cycles,
        "winner_candidate": conclusion.get("selected_solution", {}).get("winner_candidate_id", ""),
        "review_feedback_path": str(review_feedback_path),
        "review_report_path": str(review_report_path),
        "final_conclusion_json": str(conclusion_json),
        "final_conclusion_md": str(conclusion_md),
        "pipeline_summary_json": str(run_dir / "deliverables" / "pipeline_summary_inbox.json"),
        "debug_trace_jsonl": tracer.paths()["jsonl"],
        "debug_trace_json": tracer.paths()["json"],
        "debug_trace_markdown": tracer.paths()["markdown"],
    }
    save_json(run_dir / "deliverables" / "pipeline_summary_inbox.json", summary)
    _trace_event(
        tracer=tracer,
        step="pipeline.inbox.finish",
        status="ok",
        message="run_inbox_cycle finished",
        inputs={
            "latest_round": latest_round,
            "review_cycles": review_cycles,
            "final_package_message_id": final_package_msg.get("id", ""),
        },
        outputs={
            "approved": summary["approved"],
            "winner": summary["winner_candidate"],
            "pipeline_summary_json": summary["pipeline_summary_json"],
        },
        artifacts=[summary["pipeline_summary_json"], summary["final_conclusion_json"], summary["review_feedback_path"]],
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Team+Inbox research cycle without shared blackboard.")
    parser.add_argument("--run-root", required=True, help="Root directory containing runs.")
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

    summary = run_inbox_cycle(
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
        debug_enabled=not args.no_debug,
        debug_console=args.debug_console,
    )
    save_json(Path(args.run_root) / args.run_id / "deliverables" / "run_inbox_cycle_stdout.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
