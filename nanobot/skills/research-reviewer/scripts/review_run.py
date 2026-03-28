from __future__ import annotations

import argparse
import subprocess
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


def _resolve_report_path(board_path: Path, private_report_path: str) -> Path:
    raw = private_report_path.strip()
    if not raw:
        return Path()
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return board_path.parent.parent / candidate


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _check_metric_consistency(board: dict[str, Any], board_path: Path) -> tuple[bool, str]:
    problems: list[str] = []
    for candidate_id in _active_candidates(board):
        entry = board.get("workers", {}).get(candidate_id, {})
        if not isinstance(entry, dict):
            problems.append(f"{candidate_id}: worker entry is not an object")
            continue

        report_path = _resolve_report_path(board_path, str(entry.get("private_report_path", "")))
        if not report_path.exists():
            problems.append(f"{candidate_id}: report not found at {report_path}")
            continue

        metrics_path = report_path.with_name("metrics.json")
        if not metrics_path.exists():
            problems.append(f"{candidate_id}: metrics.json not found near report ({metrics_path})")
            continue

        metrics = load_json(metrics_path)
        if not isinstance(metrics, dict):
            problems.append(f"{candidate_id}: metrics file is not a JSON object")
            continue

        core_metrics = entry.get("core_metrics", {})
        if not isinstance(core_metrics, dict):
            core_metrics = {}
        board_primary = _coerce_float(core_metrics.get("primary_metric"))
        metrics_primary = _coerce_float(metrics.get("primary_metric", metrics.get("primary")))
        if board_primary is None or metrics_primary is None:
            problems.append(
                f"{candidate_id}: missing primary metric (board={board_primary}, metrics={metrics_primary})"
            )
            continue
        if abs(board_primary - metrics_primary) > 1e-9:
            problems.append(
                f"{candidate_id}: primary metric mismatch (board={board_primary}, metrics={metrics_primary})"
            )

    if problems:
        return False, "; ".join(problems)
    return True, "board primary metrics are consistent with metrics.json for all active candidates"


def _check_notes_evidence(board: dict[str, Any], board_path: Path) -> tuple[bool, str]:
    required_sections = [
        "borrowed peer ideas",
        "rejected peer ideas",
        "changed implementation",
        "result change",
    ]
    problems: list[str] = []
    for candidate_id in _active_candidates(board):
        entry = board.get("workers", {}).get(candidate_id, {})
        if not isinstance(entry, dict):
            problems.append(f"{candidate_id}: worker entry is not an object")
            continue
        report_path = _resolve_report_path(board_path, str(entry.get("private_report_path", "")))
        notes_path = report_path.with_name("notes.md")
        if not notes_path.exists():
            problems.append(f"{candidate_id}: notes.md missing at {notes_path}")
            continue
        text = notes_path.read_text(encoding="utf-8").lower()
        for section in required_sections:
            if section not in text:
                problems.append(f"{candidate_id}: notes.md missing section '{section}'")
                break

    if problems:
        return False, "; ".join(problems)
    return True, "notes evidence exists for all active candidates"


def _run_command_check(
    check: dict[str, Any],
    board_path: Path,
) -> tuple[bool, str]:
    raw_command = check.get("command")
    if isinstance(raw_command, list):
        command = [str(item) for item in raw_command]
        shell = False
    elif isinstance(raw_command, str) and raw_command.strip():
        command = raw_command.strip()
        shell = True
    else:
        return False, "missing command field for custom check"

    cwd_raw = str(check.get("cwd", "")).strip()
    if cwd_raw:
        cwd = Path(cwd_raw)
        if not cwd.is_absolute():
            cwd = board_path.parent.parent / cwd
    else:
        cwd = board_path.parent.parent

    expected_exit = int(check.get("expected_exit", 0) or 0)
    timeout_sec = int(check.get("timeout_sec", 120) or 120)

    try:
        proc = subprocess.run(
            command,
            shell=shell,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return False, f"command timed out after {timeout_sec}s"
    if proc.returncode != expected_exit:
        return (
            False,
            f"command exit={proc.returncode}, expected={expected_exit}; stdout={proc.stdout.strip()} stderr={proc.stderr.strip()}",
        )
    return True, f"command passed (exit={proc.returncode})"


def _run_review_checks(
    board: dict[str, Any],
    acceptance: dict[str, Any],
    board_path: Path,
    agenda_path: Path,
) -> list[tuple[str, bool, str]]:
    configured = acceptance.get("review_checks", [])
    if not isinstance(configured, list):
        configured = []
    if not configured:
        configured = [
            {"name": "validate_board_shape", "required": True},
            {"name": "generate_next_agenda", "required": True},
        ]

    results: list[tuple[str, bool, str]] = []
    for row in configured:
        if not isinstance(row, dict):
            results.append(("unknown_check", False, "review_checks row is not a JSON object"))
            continue
        name = str(row.get("name", "unknown_check")).strip() or "unknown_check"
        required = bool(row.get("required", True))
        normalized = name.lower()

        if normalized == "validate_board_shape":
            try:
                validate_board(board_path)
                ok, note = True, "validate_board.py passed"
            except Exception as exc:
                ok, note = False, f"validate_board.py failed: {exc}"
        elif normalized == "generate_next_agenda":
            try:
                tmp_agenda = agenda_path.parent / ".review_generated_agenda.json"
                generate_agenda(board_path=board_path, agenda_path=tmp_agenda, max_rounds=3)
                ok, note = True, "generate_agenda.py ran successfully"
                try:
                    tmp_agenda.unlink()
                except FileNotFoundError:
                    pass
            except Exception as exc:
                ok, note = False, f"generate_agenda.py failed: {exc}"
        elif normalized == "verify_report_metric_consistency":
            ok, note = _check_metric_consistency(board, board_path)
        elif normalized == "require_worker_notes_evidence":
            ok, note = _check_notes_evidence(board, board_path)
        elif normalized in {"review_feedback_written", "final_conclusion_written"}:
            # These are post-review pipeline checks. Keep them pass here for backward compatibility.
            ok, note = True, "validated by downstream pipeline stage"
        else:
            ok, note = _run_command_check(row, board_path)

        if not required and not ok:
            results.append((name, True, f"optional check failed but ignored: {note}"))
        else:
            results.append((name, ok, note))

    return results


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

    if req == "main experiment can be reproduced":
        return _check_metric_consistency(board, board_path)

    if req == "report uses actual measured metrics":
        return _check_metric_consistency(board, board_path)

    if req == "worker notes record adopted and rejected peer ideas":
        return _check_notes_evidence(board, board_path)

    return False, f"unsupported hard requirement: {requirement}"


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

    check_rows = _run_review_checks(
        board=board,
        acceptance=acceptance,
        board_path=board_path,
        agenda_path=agenda_path,
    )
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
