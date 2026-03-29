from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "research-blackboard" / "scripts"
import sys

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from research_board_lib import load_json, normalize_lines, save_json

REQUIRED_ENVELOPE = {
    "id",
    "run_id",
    "round",
    "from",
    "to",
    "type",
    "correlation_id",
    "ts_utc",
    "payload",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _extract_candidates(path: Path) -> list[str]:
    payload = load_json(path)
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("candidates"), list):
        rows = payload["candidates"]
    else:
        rows = []
    out: list[str] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("candidateId") or item.get("candidate_id") or "").strip()
        if cid:
            out.append(cid)
    return out


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_path(run_dir: Path, raw: str) -> Path:
    text = raw.strip()
    if not text:
        return Path()
    path = Path(text)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return run_dir / path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_worker_updates(
    *,
    inbox_rows: dict[str, list[dict[str, Any]]],
    candidate_ids: list[str],
) -> dict[str, dict[str, Any]]:
    implementer_rows = inbox_rows.get("implementer", [])
    latest: dict[str, dict[str, Any]] = {}
    for row in implementer_rows:
        if str(row.get("type", "")) != "worker_round_update":
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        candidate_id = str(payload.get("candidate_id", "")).strip()
        if candidate_id not in candidate_ids:
            continue
        round_idx = int(row.get("round", 0) or 0)
        prev = latest.get(candidate_id)
        prev_round = int(prev.get("round", 0) or 0) if prev else -1
        if round_idx >= prev_round:
            latest[candidate_id] = row
    return latest


def _check_inbox_metric_consistency(
    *,
    run_dir: Path,
    inbox_rows: dict[str, list[dict[str, Any]]],
    candidate_ids: list[str],
) -> tuple[bool, str]:
    updates = _latest_worker_updates(inbox_rows=inbox_rows, candidate_ids=candidate_ids)
    issues: list[str] = []
    for candidate_id in candidate_ids:
        row = updates.get(candidate_id)
        if not isinstance(row, dict):
            issues.append(f"{candidate_id}: missing worker_round_update")
            continue
        payload = row.get("payload", {})
        if not isinstance(payload, dict):
            issues.append(f"{candidate_id}: payload is not object")
            continue
        report_path = _resolve_path(run_dir, str(payload.get("private_report_ref", "")))
        metrics_path = report_path.with_name("metrics.json")
        if not report_path.exists():
            issues.append(f"{candidate_id}: report not found ({report_path})")
            continue
        if not metrics_path.exists():
            issues.append(f"{candidate_id}: metrics not found ({metrics_path})")
            continue
        metrics = load_json(metrics_path)
        if not isinstance(metrics, dict):
            issues.append(f"{candidate_id}: metrics file is not JSON object")
            continue
        payload_core = payload.get("core_metrics", {})
        if not isinstance(payload_core, dict):
            payload_core = {}
        payload_primary = _coerce_float(payload_core.get("primary_metric"))
        metrics_primary = _coerce_float(metrics.get("primary_metric", metrics.get("primary")))
        if payload_primary is None or metrics_primary is None:
            issues.append(f"{candidate_id}: missing primary metric in payload/metrics")
            continue
        if abs(payload_primary - metrics_primary) > 1e-9:
            issues.append(f"{candidate_id}: primary mismatch payload={payload_primary} metrics={metrics_primary}")

    if issues:
        return False, "; ".join(issues)
    return True, "worker payload primary metrics match metrics.json for all candidates"


def _check_worker_notes_evidence(
    *,
    run_dir: Path,
    inbox_rows: dict[str, list[dict[str, Any]]],
    candidate_ids: list[str],
) -> tuple[bool, str]:
    updates = _latest_worker_updates(inbox_rows=inbox_rows, candidate_ids=candidate_ids)
    required_sections = [
        "borrowed peer ideas",
        "rejected peer ideas",
        "changed implementation",
        "result change",
    ]
    issues: list[str] = []
    for candidate_id in candidate_ids:
        row = updates.get(candidate_id)
        if not isinstance(row, dict):
            issues.append(f"{candidate_id}: missing worker_round_update")
            continue
        payload = row.get("payload", {})
        if not isinstance(payload, dict):
            issues.append(f"{candidate_id}: payload is not object")
            continue
        notes_ref = str(payload.get("notes_ref", "")).strip()
        if notes_ref:
            notes_path = _resolve_path(run_dir, notes_ref)
        else:
            report_path = _resolve_path(run_dir, str(payload.get("private_report_ref", "")))
            notes_path = report_path.with_name("notes.md")
        if not notes_path.exists():
            issues.append(f"{candidate_id}: notes file missing ({notes_path})")
            continue
        text = notes_path.read_text(encoding="utf-8").lower()
        for section in required_sections:
            if section not in text:
                issues.append(f"{candidate_id}: notes missing section '{section}'")
                break

    if issues:
        return False, "; ".join(issues)
    return True, "worker notes include adopted/rejected/change/result evidence for all candidates"


def _check_execution_evidence(
    *,
    run_dir: Path,
    inbox_rows: dict[str, list[dict[str, Any]]],
    candidate_ids: list[str],
    require_live_mode: bool,
) -> tuple[bool, str]:
    updates = _latest_worker_updates(inbox_rows=inbox_rows, candidate_ids=candidate_ids)
    issues: list[str] = []
    for candidate_id in candidate_ids:
        row = updates.get(candidate_id)
        if not isinstance(row, dict):
            issues.append(f"{candidate_id}: missing worker_round_update")
            continue
        payload = row.get("payload", {})
        if not isinstance(payload, dict):
            issues.append(f"{candidate_id}: payload is not object")
            continue

        execution_mode = str(payload.get("execution_mode", "")).strip()
        if not execution_mode:
            issues.append(f"{candidate_id}: missing execution_mode")
            continue
        if require_live_mode and execution_mode == "replay_import":
            issues.append(f"{candidate_id}: execution_mode is replay_import (live required)")

        report_path = _resolve_path(run_dir, str(payload.get("private_report_ref", "")))
        metrics_path = report_path.with_name("metrics.json")
        if not report_path.exists() or not metrics_path.exists():
            issues.append(f"{candidate_id}: missing report/metrics artifacts")
            continue

        log_path = _resolve_path(run_dir, str(payload.get("execution_log_ref", "")))
        if not log_path.exists():
            issues.append(f"{candidate_id}: execution_log missing ({log_path})")
            continue
        log_payload = load_json(log_path)
        if not isinstance(log_payload, dict):
            issues.append(f"{candidate_id}: execution_log is not JSON object")
            continue

        log_mode = str(log_payload.get("execution_mode", "")).strip()
        if log_mode != execution_mode:
            issues.append(f"{candidate_id}: execution_mode mismatch payload={execution_mode} log={log_mode}")

        output_hashes = log_payload.get("output_hashes", {})
        if not isinstance(output_hashes, dict):
            output_hashes = {}
        expected_report_hash = str(output_hashes.get("report_sha256", "")).strip()
        expected_metrics_hash = str(output_hashes.get("metrics_sha256", "")).strip()
        if not expected_report_hash or not expected_metrics_hash:
            issues.append(f"{candidate_id}: execution_log missing output hashes")
            continue

        if _sha256(report_path) != expected_report_hash:
            issues.append(f"{candidate_id}: report hash mismatch")
        if _sha256(metrics_path) != expected_metrics_hash:
            issues.append(f"{candidate_id}: metrics hash mismatch")

    if issues:
        return False, "; ".join(issues)
    return True, "execution logs and artifact hashes are valid for all candidates"


def _check_hard_requirement(
    requirement: str,
    *,
    run_dir: Path,
    inbox_rows: dict[str, list[dict[str, Any]]],
    candidate_ids: list[str],
) -> tuple[bool, str]:
    req = requirement.strip().lower()
    all_rows = [row for rows in inbox_rows.values() for row in rows]

    if req == "shared board can be initialized":
        expected_roles = ["implementer", "reviewer"] + [f"worker_{i + 1:02d}" for i in range(len(candidate_ids))]
        missing = [role for role in expected_roles if role not in inbox_rows]
        return len(missing) == 0, "inbox channels initialized" if not missing else f"missing inbox roles: {', '.join(missing)}"

    if req == "worker digests can be published":
        implementer_rows = inbox_rows.get("implementer", [])
        seen = {
            str((row.get("payload") or {}).get("candidate_id", "")).strip()
            for row in implementer_rows
            if str(row.get("type", "")) == "worker_round_update"
        }
        ok = all(candidate in seen for candidate in candidate_ids)
        return ok, "worker_round_update exists for all candidates"

    if req == "peer feedback can be merged":
        count = sum(1 for row in all_rows if str(row.get("type", "")) in {"peer_key_insight", "improvement_proposal"})
        return count > 0, f"peer insight/improvement messages: {count}"

    if req == "agenda can be generated from board findings":
        count = sum(1 for row in all_rows if str(row.get("type", "")) == "round_synthesis_ready")
        return count > 0, f"round_synthesis_ready messages: {count}"

    if req == "review feedback can be generated with tool evidence":
        return True, "review tool executed and evidence generated"

    if req == "final conclusion artifacts can be generated":
        summary_dir = run_dir / "runtime" / "round_summaries"
        has_round_summary = summary_dir.exists() and any(summary_dir.glob("round_*.json"))
        review_request_count = sum(1 for row in all_rows if str(row.get("type", "")) == "review_request")
        ok = has_round_summary and review_request_count > 0
        note = f"round_summaries_ready={str(has_round_summary).lower()}, review_request_messages={review_request_count}"
        return ok, note

    if req == "main experiment can be reproduced":
        return _check_execution_evidence(
            run_dir=run_dir,
            inbox_rows=inbox_rows,
            candidate_ids=candidate_ids,
            require_live_mode=True,
        )

    if req == "report uses actual measured metrics":
        return _check_inbox_metric_consistency(
            run_dir=run_dir,
            inbox_rows=inbox_rows,
            candidate_ids=candidate_ids,
        )

    if req == "worker notes record adopted and rejected peer ideas":
        return _check_worker_notes_evidence(
            run_dir=run_dir,
            inbox_rows=inbox_rows,
            candidate_ids=candidate_ids,
        )

    return False, f"unsupported hard requirement: {requirement}"


def _run_review_checks(
    *,
    run_dir: Path,
    inbox_rows: dict[str, list[dict[str, Any]]],
    candidate_ids: list[str],
    acceptance: dict[str, Any],
) -> list[tuple[str, bool, str]]:
    configured = acceptance.get("review_checks", [])
    if not isinstance(configured, list):
        configured = []
    if not configured:
        configured = [
            {"name": "validate_inbox_envelope", "required": True},
            {"name": "validate_candidate_coverage", "required": True},
        ]

    checks: list[tuple[str, bool, str]] = []
    for row in configured:
        if not isinstance(row, dict):
            checks.append(("unknown_check", False, "review_checks row must be a JSON object"))
            continue
        name = str(row.get("name", "unknown_check")).strip() or "unknown_check"
        required = bool(row.get("required", True))
        normalized = name.lower()

        if normalized == "validate_inbox_envelope":
            bad: list[str] = []
            for role, rows in inbox_rows.items():
                for idx, item in enumerate(rows, start=1):
                    missing = sorted(REQUIRED_ENVELOPE - set(item))
                    if missing:
                        bad.append(f"{role}#{idx}: missing {', '.join(missing)}")
            ok = len(bad) == 0
            note = "all messages include required envelope fields" if ok else "; ".join(bad[:3])
        elif normalized == "validate_candidate_coverage":
            implementer_rows = inbox_rows.get("implementer", [])
            seen = {
                str((item.get("payload") or {}).get("candidate_id", "")).strip()
                for item in implementer_rows
                if str(item.get("type", "")) == "worker_round_update"
            }
            missing_candidates = [cid for cid in candidate_ids if cid not in seen]
            ok = len(missing_candidates) == 0
            note = "all candidates emitted worker_round_update" if ok else f"missing: {', '.join(missing_candidates)}"
        elif normalized == "validate_execution_evidence":
            ok, note = _check_execution_evidence(
                run_dir=run_dir,
                inbox_rows=inbox_rows,
                candidate_ids=candidate_ids,
                require_live_mode=False,
            )
        elif normalized == "verify_report_metric_consistency":
            ok, note = _check_inbox_metric_consistency(
                run_dir=run_dir,
                inbox_rows=inbox_rows,
                candidate_ids=candidate_ids,
            )
        elif normalized == "require_worker_notes_evidence":
            ok, note = _check_worker_notes_evidence(
                run_dir=run_dir,
                inbox_rows=inbox_rows,
                candidate_ids=candidate_ids,
            )
        else:
            ok = False
            note = f"unsupported inbox review check: {name}"

        if not required and not ok:
            checks.append((name, True, f"optional check failed but ignored: {note}"))
        else:
            checks.append((name, ok, note))

    return checks


def _write_review_report(path: Path, payload: dict[str, Any], checks: list[tuple[str, bool, str]]) -> None:
    lines: list[str] = ["# Inbox Review Report", "", f"- approved: {str(payload['approved']).lower()}", "", "## Hard Requirement Evaluation", ""]
    for item in payload["evidence"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Tool Checks", ""])
    for name, ok, note in checks:
        lines.append(f"- {name}: {'PASS' if ok else 'FAIL'}")
        lines.append(f"  - {note}")

    lines.extend(["", "## Must Fix", ""])
    if payload["must_fix"]:
        for item in payload["must_fix"]:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Optional Improvements", ""])
    if payload["optional_improvements"]:
        for item in payload["optional_improvements"]:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def review_inbox_run(
    *,
    run_dir: Path,
    acceptance_path: Path,
    output_feedback: Path,
    output_report: Path,
) -> dict[str, Any]:
    acceptance = load_json(acceptance_path)
    if not isinstance(acceptance, dict):
        raise ValueError("acceptance spec must be a JSON object")

    candidate_ids = _extract_candidates(run_dir / "plan" / "candidates.json")
    inbox_root = run_dir / "runtime" / "inbox"

    inbox_rows: dict[str, list[dict[str, Any]]] = {}
    for inbox_file in sorted(inbox_root.glob("*.jsonl")):
        inbox_rows[inbox_file.stem] = _read_jsonl(inbox_file)

    hard_requirements = normalize_lines(acceptance.get("hard_requirements"))
    soft_requirements = normalize_lines(acceptance.get("soft_requirements"))

    evidence: list[str] = []
    must_fix: list[str] = []

    for req in hard_requirements:
        ok, note = _check_hard_requirement(
            req,
            run_dir=run_dir,
            inbox_rows=inbox_rows,
            candidate_ids=candidate_ids,
        )
        evidence.append(f"{req}: {'PASS' if ok else 'FAIL'} | {note}")
        if not ok:
            must_fix.append(req)

    checks = _run_review_checks(
        run_dir=run_dir,
        inbox_rows=inbox_rows,
        candidate_ids=candidate_ids,
        acceptance=acceptance,
    )
    for name, ok, note in checks:
        evidence.append(f"{name}: {'PASS' if ok else 'FAIL'} | {note}")
        if not ok:
            must_fix.append(name)

    optional_improvements = [f"soft target to monitor: {item}" for item in soft_requirements]

    payload = {
        "approved": len(must_fix) == 0,
        "must_fix": must_fix,
        "optional_improvements": optional_improvements,
        "evidence": evidence,
    }

    save_json(output_feedback, payload)
    _write_review_report(output_report, payload, checks)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run inbox-based reviewer checks for a research run.")
    parser.add_argument("--run-dir", required=True, help="Run directory.")
    parser.add_argument("--acceptance", required=True, help="acceptance_spec.json path.")
    parser.add_argument("--output-feedback", required=True, help="Output feedback JSON path.")
    parser.add_argument("--output-report", required=True, help="Output markdown report path.")
    args = parser.parse_args()

    review_inbox_run(
        run_dir=Path(args.run_dir),
        acceptance_path=Path(args.acceptance),
        output_feedback=Path(args.output_feedback),
        output_report=Path(args.output_report),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
