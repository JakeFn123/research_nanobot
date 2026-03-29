from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from research_board_lib import ensure_board_shape, load_json, normalize_lines, save_json


def _resolve_acceptance_spec(board_path: Path, explicit_path: Path | None) -> dict[str, Any] | None:
    if explicit_path is not None:
        return load_json(explicit_path)

    board = ensure_board_shape(load_json(board_path))
    rel = str(board.get("acceptance_spec_path", "")).strip()
    if not rel:
        return None

    candidate_path = board_path.parent.parent / rel
    if not candidate_path.exists():
        return None
    return load_json(candidate_path)


def _candidate_rows(board: dict[str, Any]) -> list[dict[str, Any]]:
    findings = board.get("global_findings", {})
    rank_hint = findings.get("candidate_rank_hint", [])

    by_hint: dict[str, dict[str, Any]] = {}
    if isinstance(rank_hint, list):
        for row in rank_hint:
            if not isinstance(row, dict):
                continue
            cid = str(row.get("candidate_id", "")).strip()
            if cid:
                by_hint[cid] = row

    rows: list[dict[str, Any]] = []
    for candidate_id, entry in board.get("workers", {}).items():
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "active")).strip().lower()
        if status in {"dropped", "archived", "failed"}:
            continue

        metrics = entry.get("core_metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}
        row_hint = by_hint.get(candidate_id, {})

        rows.append(
            {
                "candidate_id": candidate_id,
                "plan_name": str(entry.get("plan_name", "")).strip(),
                "status": status,
                "primary_metric": metrics.get("primary_metric"),
                "praise_score": int(row_hint.get("praise_score", 0) or 0),
                "concern_score": int(row_hint.get("concern_score", 0) or 0),
                "strengths": normalize_lines(entry.get("strengths")),
                "weaknesses": normalize_lines(entry.get("weaknesses")),
                "next_move": normalize_lines(entry.get("proposed_next_move")),
            }
        )

    return sorted(
        rows,
        key=lambda item: (
            item["primary_metric"] is None,
            -(item["primary_metric"] or 0.0),
            -item["praise_score"],
            item["concern_score"],
        ),
    )


def _coerce_review_feedback(review_feedback: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(review_feedback, dict):
        return {
            "approved": None,
            "must_fix": [],
            "optional_improvements": [],
            "evidence": [],
        }

    approved_raw = review_feedback.get("approved")
    approved: bool | None
    if isinstance(approved_raw, bool):
        approved = approved_raw
    else:
        approved = None

    return {
        "approved": approved,
        "must_fix": normalize_lines(review_feedback.get("must_fix")),
        "optional_improvements": normalize_lines(review_feedback.get("optional_improvements")),
        "evidence": normalize_lines(review_feedback.get("evidence")),
    }


def _acceptance_summary(acceptance_spec: dict[str, Any] | None, review_feedback: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(acceptance_spec, dict):
        return {
            "hard_requirements": [],
            "soft_requirements": [],
            "review_checks": [],
            "status": "not_provided",
        }

    approved = review_feedback.get("approved")
    if approved is True:
        status = "approved"
    elif approved is False:
        status = "rejected"
    else:
        status = "pending_review"

    return {
        "hard_requirements": normalize_lines(acceptance_spec.get("hard_requirements")),
        "soft_requirements": normalize_lines(acceptance_spec.get("soft_requirements")),
        "review_checks": acceptance_spec.get("review_checks", []),
        "status": status,
    }


def _build_conclusion_markdown(conclusion: dict[str, Any]) -> str:
    selected = conclusion["selected_solution"]
    readiness = conclusion["readiness"]
    evidence = conclusion["evidence_summary"]

    lines: list[str] = []
    lines.append("# Final Conclusion")
    lines.append("")
    lines.append(f"- run_id: {conclusion['run_id']}")
    lines.append(f"- problem: {conclusion['problem']}")
    lines.append(f"- review_status: {readiness['review_status']}")
    lines.append(f"- ready_for_delivery: {str(readiness['ready_for_delivery']).lower()}")
    lines.append("")
    lines.append("## Selected Solution")
    lines.append("")
    lines.append(f"- strategy: {selected['strategy']}")
    lines.append(f"- winner_candidate_id: {selected['winner_candidate_id']}")
    lines.append(f"- winner_plan_name: {selected['winner_plan_name']}")

    supporting = selected.get("supporting_candidates", [])
    if supporting:
        lines.append("- supporting_candidates:")
        for item in supporting:
            lines.append(f"  - {item}")

    lines.append("")
    lines.append("## Key Evidence")
    lines.append("")
    lines.append("### Dominant Strengths")
    if evidence["dominant_strengths"]:
        for item in evidence["dominant_strengths"]:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("### Dominant Failures")
    if evidence["dominant_failures"]:
        for item in evidence["dominant_failures"]:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("### Improvement Targets")
    if evidence["improvement_targets"]:
        for item in evidence["improvement_targets"]:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("## Reviewer Feedback")
    lines.append("")

    must_fix = conclusion["review_feedback"]["must_fix"]
    optional = conclusion["review_feedback"]["optional_improvements"]

    lines.append("### Must Fix")
    if must_fix:
        for item in must_fix:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("### Optional Improvements")
    if optional:
        for item in optional:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("## Final Recommendation")
    lines.append("")
    lines.append(conclusion["final_recommendation"])

    lines.append("")
    lines.append("## Next Actions")
    lines.append("")
    next_actions = conclusion["next_actions"]
    if next_actions:
        for item in next_actions:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    return "\n".join(lines) + "\n"


def finalize_conclusion(
    board_path: Path,
    agenda_path: Path,
    output_json: Path,
    output_md: Path,
    review_feedback_path: Path | None = None,
    acceptance_spec_path: Path | None = None,
) -> dict[str, Any]:
    board = ensure_board_shape(load_json(board_path))
    agenda = load_json(agenda_path)
    if not isinstance(agenda, dict):
        raise ValueError("agenda.json must be a JSON object.")

    review_feedback_raw = load_json(review_feedback_path) if review_feedback_path else None
    review_feedback = _coerce_review_feedback(review_feedback_raw)

    acceptance_spec = _resolve_acceptance_spec(board_path, acceptance_spec_path)
    acceptance_summary = _acceptance_summary(acceptance_spec, review_feedback)

    rows = _candidate_rows(board)
    winner = rows[0] if rows else None
    supporting_candidates = [row["candidate_id"] for row in rows[1:3]]

    findings = board.get("global_findings", {})
    dominant_strengths = normalize_lines(findings.get("dominant_strengths"))
    dominant_failures = normalize_lines(findings.get("dominant_failures"))
    improvement_targets = normalize_lines(findings.get("improvement_targets"))

    approved = review_feedback["approved"]
    if approved is True:
        review_status = "approved"
        ready_for_delivery = True
    elif approved is False:
        review_status = "rejected"
        ready_for_delivery = False
    else:
        review_status = "pending_review"
        ready_for_delivery = False

    if winner is None:
        strategy = "undetermined"
        winner_candidate_id = ""
        winner_plan_name = ""
    elif supporting_candidates and dominant_strengths:
        strategy = "fusion"
        winner_candidate_id = winner["candidate_id"]
        winner_plan_name = winner["plan_name"]
    else:
        strategy = "single"
        winner_candidate_id = winner["candidate_id"]
        winner_plan_name = winner["plan_name"]

    final_recommendation: str
    next_actions: list[str]
    if review_status == "approved":
        final_recommendation = (
            f"Deploy {winner_candidate_id or 'the top candidate'} as the final baseline and keep a short monitoring window."
        )
        next_actions = [
            "Package final report and reproducible artifacts.",
            "Run one safety regression check before release.",
        ]
    elif review_status == "rejected":
        must_fix = review_feedback["must_fix"]
        final_recommendation = (
            "Do not finalize yet. Return to implementer loop and address reviewer must-fix items first."
        )
        next_actions = must_fix or ["Address reviewer must-fix items and rerun evaluation."]
    else:
        final_recommendation = (
            "Generate reviewer evidence and decision first, then re-run finalization for a release-grade conclusion."
        )
        next_actions = [
            "Produce reviewer_feedback.json with approved/must_fix/evidence fields.",
            "Re-run finalize_conclusion.py after reviewer decision.",
        ]

    conclusion = {
        "run_id": str(board.get("run_id", "")).strip(),
        "problem": str(board.get("problem", "")).strip(),
        "round_index": int(agenda.get("round_index", board.get("round_index", 0)) or 0),
        "readiness": {
            "review_status": review_status,
            "ready_for_delivery": ready_for_delivery,
        },
        "selected_solution": {
            "strategy": strategy,
            "winner_candidate_id": winner_candidate_id,
            "winner_plan_name": winner_plan_name,
            "supporting_candidates": supporting_candidates,
        },
        "evidence_summary": {
            "dominant_strengths": dominant_strengths,
            "dominant_failures": dominant_failures,
            "improvement_targets": improvement_targets,
            "candidate_rank_hint": findings.get("candidate_rank_hint", []),
        },
        "review_feedback": review_feedback,
        "acceptance_summary": acceptance_summary,
        "final_recommendation": final_recommendation,
        "next_actions": next_actions,
    }

    save_json(output_json, conclusion)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(_build_conclusion_markdown(conclusion), encoding="utf-8")
    return conclusion


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate final conclusion artifacts from board and agenda.")
    parser.add_argument("--board", required=True, help="Path to worker_board.json.")
    parser.add_argument("--agenda", required=True, help="Path to agenda.json.")
    parser.add_argument("--output-json", required=True, help="Output path for final_conclusion.json.")
    parser.add_argument("--output-md", required=True, help="Output path for final_conclusion.md.")
    parser.add_argument("--review-feedback", help="Optional reviewer feedback json path.")
    parser.add_argument("--acceptance-spec", help="Optional acceptance spec json path.")
    args = parser.parse_args()

    finalize_conclusion(
        board_path=Path(args.board),
        agenda_path=Path(args.agenda),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
        review_feedback_path=Path(args.review_feedback) if args.review_feedback else None,
        acceptance_spec_path=Path(args.acceptance_spec) if args.acceptance_spec else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
