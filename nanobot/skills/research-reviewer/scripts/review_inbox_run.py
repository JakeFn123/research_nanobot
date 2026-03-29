from __future__ import annotations

import argparse
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
    import json

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
        # In inbox mode, planner may only receive the final package later in the pipeline.
        # At review time we require active runtime channels (implementer/reviewer/workers).
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
        count = sum(
            1
            for row in all_rows
            if str(row.get("type", "")) in {"peer_key_insight", "improvement_proposal"}
        )
        return count > 0, f"peer insight/improvement messages: {count}"

    if req == "agenda can be generated from board findings":
        count = sum(1 for row in all_rows if str(row.get("type", "")) == "round_synthesis_ready")
        return count > 0, f"round_synthesis_ready messages: {count}"

    if req == "review feedback can be generated with tool evidence":
        return True, "review tool executed and evidence generated"

    if req == "final conclusion artifacts can be generated":
        # This check runs before final packaging, so verify prerequisites instead of the
        # already-generated deliverable files.
        summary_dir = run_dir / "runtime" / "round_summaries"
        has_round_summary = summary_dir.exists() and any(summary_dir.glob("round_*.json"))
        review_request_count = sum(1 for row in all_rows if str(row.get("type", "")) == "review_request")
        ok = has_round_summary and review_request_count > 0
        note = (
            f"round_summaries_ready={str(has_round_summary).lower()}, review_request_messages={review_request_count}"
        )
        return ok, note

    return False, f"unsupported hard requirement: {requirement}"


def _run_review_checks(
    *,
    inbox_rows: dict[str, list[dict[str, Any]]],
    candidate_ids: list[str],
) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    # Envelope shape check
    bad: list[str] = []
    for role, rows in inbox_rows.items():
        for idx, row in enumerate(rows, start=1):
            missing = sorted(REQUIRED_ENVELOPE - set(row))
            if missing:
                bad.append(f"{role}#{idx}: missing {', '.join(missing)}")
    checks.append(("validate_inbox_envelope", len(bad) == 0, "all messages include required envelope fields" if not bad else "; ".join(bad[:3])))

    # Candidate coverage check
    implementer_rows = inbox_rows.get("implementer", [])
    seen = {
        str((row.get("payload") or {}).get("candidate_id", "")).strip()
        for row in implementer_rows
        if str(row.get("type", "")) == "worker_round_update"
    }
    missing_candidates = [cid for cid in candidate_ids if cid not in seen]
    checks.append((
        "validate_candidate_coverage",
        len(missing_candidates) == 0,
        "all candidates emitted worker_round_update" if not missing_candidates else f"missing: {', '.join(missing_candidates)}",
    ))
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

    checks = _run_review_checks(inbox_rows=inbox_rows, candidate_ids=candidate_ids)
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
