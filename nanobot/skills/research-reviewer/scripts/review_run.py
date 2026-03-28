from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "research-blackboard" / "scripts"
import sys

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_agenda import generate_agenda
from research_board_lib import ensure_board_shape, load_json, normalize_lines, save_json
from validate_board import validate_board


def _active_candidates(board: dict[str, Any]) -> list[str]:
    output: list[str] = []
    for candidate_id, entry in board.get("workers", {}).items():
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "active")).strip().lower()
        if status not in {"dropped", "archived", "failed"}:
            output.append(candidate_id)
    return output


def _check_hard_requirement(
    requirement: str,
    board: dict[str, Any],
    agenda: dict[str, Any],
    board_path: Path,
    agenda_path: Path,
) -> tuple[bool, str]:
    req = requirement.strip().lower()

    if req == "shared board can be initialized":
        ok = board_path.exists() and isinstance(board.get("workers"), dict)
        return ok, "board file exists and workers object is present"

    if req == "worker digests can be published":
        active = _active_candidates(board)
        ok = bool(active)
        if ok:
            for cid in active:
                entry = board["workers"].get(cid, {})
                if int(entry.get("round", 0) or 0) <= 0:
                    ok = False
                    break
        return ok, "active workers have round > 0 digests"

    if req == "peer feedback can be merged":
        feedback = board.get("peer_feedback", {})
        ok = isinstance(feedback, dict) and len(feedback) > 0
        return ok, "peer_feedback contains at least one structured feedback item"

    if req == "agenda can be generated from board findings":
        qs = normalize_lines(agenda.get("priority_questions")) if isinstance(agenda, dict) else []
        ok = agenda_path.exists() and len(qs) > 0
        return ok, "agenda exists and contains non-empty priority questions"

    if req == "review feedback can be generated with tool evidence":
        return True, "review tool executed and evidence list will be written"

    if req == "final conclusion artifacts can be generated":
        ok = board_path.exists() and agenda_path.exists()
        return ok, "board+agenda prerequisites for finalize_conclusion are available"

    # Unknown requirement: keep conservative and mark unresolved.
    return False, f"unsupported hard requirement: {requirement}"


def _run_review_checks(board_path: Path, agenda_path: Path) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    try:
        validate_board(board_path)
        results.append(("validate_board_shape", True, "validate_board.py passed"))
    except Exception as exc:
        results.append(("validate_board_shape", False, f"validate_board.py failed: {exc}"))

    try:
        tmp_agenda = agenda_path.parent / ".review_generated_agenda.json"
        generate_agenda(board_path=board_path, agenda_path=tmp_agenda, max_rounds=3)
        results.append(("generate_next_agenda", True, "generate_agenda.py ran successfully"))
        try:
            tmp_agenda.unlink()
        except FileNotFoundError:
            pass
    except Exception as exc:
        results.append(("generate_next_agenda", False, f"generate_agenda.py failed: {exc}"))

    return results


def _write_review_report(path: Path, payload: dict[str, Any], check_rows: list[tuple[str, bool, str]]) -> None:
    lines: list[str] = []
    lines.append("# Review Report")
    lines.append("")
    lines.append(f"- approved: {str(payload['approved']).lower()}")
    lines.append("")
    lines.append("## Hard Requirement Evaluation")
    lines.append("")
    for item in payload["evidence"]:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("## Tool Checks")
    lines.append("")
    for name, ok, note in check_rows:
        lines.append(f"- {name}: {'PASS' if ok else 'FAIL'}")
        lines.append(f"  - {note}")

    lines.append("")
    lines.append("## Must Fix")
    lines.append("")
    must_fix = payload["must_fix"]
    if must_fix:
        for item in must_fix:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("## Optional Improvements")
    lines.append("")
    optional = payload["optional_improvements"]
    if optional:
        for item in optional:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def review_run(
    board_path: Path,
    agenda_path: Path,
    acceptance_path: Path,
    output_feedback: Path,
    output_report: Path,
) -> dict[str, Any]:
    board = ensure_board_shape(load_json(board_path))
    agenda = load_json(agenda_path)
    acceptance = load_json(acceptance_path)

    if not isinstance(agenda, dict):
        raise ValueError("agenda.json must be a JSON object")
    if not isinstance(acceptance, dict):
        raise ValueError("acceptance_spec.json must be a JSON object")

    hard = normalize_lines(acceptance.get("hard_requirements"))
    soft = normalize_lines(acceptance.get("soft_requirements"))

    must_fix: list[str] = []
    evidence: list[str] = []

    for req in hard:
        ok, note = _check_hard_requirement(req, board, agenda, board_path, agenda_path)
        evidence.append(f"{req}: {'PASS' if ok else 'FAIL'} | {note}")
        if not ok:
            must_fix.append(req)

    check_rows = _run_review_checks(board_path, agenda_path)
    for name, ok, note in check_rows:
        evidence.append(f"{name}: {'PASS' if ok else 'FAIL'} | {note}")
        if not ok:
            must_fix.append(name)

    optional_improvements: list[str] = []
    findings = board.get("global_findings", {})
    if not normalize_lines(findings.get("improvement_targets")):
        optional_improvements.append("improvement_targets is empty; add clearer cross-worker improvements")
    if not normalize_lines(agenda.get("priority_questions")):
        optional_improvements.append("agenda priority questions should be non-empty")

    for req in soft:
        optional_improvements.append(f"soft target to monitor: {req}")

    # Deduplicate while keeping order.
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item.strip())
        return out

    must_fix = _dedupe(must_fix)
    optional_improvements = _dedupe(optional_improvements)

    payload = {
        "approved": len(must_fix) == 0,
        "must_fix": must_fix,
        "optional_improvements": optional_improvements,
        "evidence": evidence,
    }

    save_json(output_feedback, payload)
    _write_review_report(output_report, payload, check_rows)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run tool-grounded reviewer checks for a research run.")
    parser.add_argument("--board", required=True, help="Path to worker_board.json")
    parser.add_argument("--agenda", required=True, help="Path to agenda.json")
    parser.add_argument("--acceptance", required=True, help="Path to acceptance_spec.json")
    parser.add_argument("--output-feedback", required=True, help="Path to review_feedback.json")
    parser.add_argument("--output-report", required=True, help="Path to review_report.md")
    args = parser.parse_args()

    review_run(
        board_path=Path(args.board),
        agenda_path=Path(args.agenda),
        acceptance_path=Path(args.acceptance),
        output_feedback=Path(args.output_feedback),
        output_report=Path(args.output_report),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
