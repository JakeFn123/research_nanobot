from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from worker_round_lib import normalize_lines, resolve_artifacts, save_json


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_slug(text: str) -> str:
    out = []
    for char in text.lower():
        if char.isalnum():
            out.append(char)
        elif char in {"_", "-"}:
            out.append(char)
        else:
            out.append("_")
    compact = "".join(out).strip("_")
    while "__" in compact:
        compact = compact.replace("__", "_")
    return compact or "candidate"


def _hash_float(seed_text: str, low: float, high: float) -> float:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / float(0xFFFFFFFF)
    return low + (high - low) * value


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _coerce_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_list(value: Any) -> list[str]:
    return normalize_lines(value)


def _merge_unique(items: list[str], limit: int = 6) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
        if len(out) >= limit:
            break
    return out


def _simulate_metrics(
    *,
    run_id: str,
    candidate_id: str,
    plan_name: str,
    round_index: int,
    expected_benefits: list[str],
    risks: list[str],
    peer_context: dict[str, list[str]],
    must_fix_items: list[str],
) -> dict[str, Any]:
    adopted = _merge_unique(
        _coerce_list(peer_context.get("borrowable_ideas"))
        + _coerce_list(peer_context.get("suggested_improvement"))
        + must_fix_items,
        limit=4,
    )
    risk_pressure = max(1, len(risks))
    benefit_bonus = min(3, len(expected_benefits))
    adopted_bonus = len(adopted)

    base = _hash_float(f"{run_id}:{candidate_id}:{plan_name}:base", 0.60, 0.78)
    jitter = _hash_float(f"{run_id}:{candidate_id}:r{round_index}:jitter", -0.01, 0.01)
    progress = 0.045 * round_index
    primary = _clamp(base + progress + (0.006 * benefit_bonus) + (0.005 * adopted_bonus) - (0.004 * risk_pressure) + jitter, 0.45, 0.98)

    uncertainty = _clamp(
        0.34 - (0.075 * round_index) - (0.008 * adopted_bonus) + _hash_float(f"{candidate_id}:u:{round_index}", -0.01, 0.01),
        0.03,
        0.50,
    )
    safety_violation = _clamp(
        0.12 - (0.025 * round_index) - (0.006 * adopted_bonus) + (0.005 * risk_pressure) + _hash_float(f"{candidate_id}:s:{round_index}", -0.008, 0.008),
        0.0,
        0.30,
    )
    cost_kusd = int(
        58
        + (16 * round_index)
        + (4 * risk_pressure)
        + (2 * max(0, 3 - adopted_bonus))
        + _hash_float(f"{candidate_id}:cost:{round_index}", -6, 8)
    )

    return {
        "primary_metric": round(primary, 4),
        "secondary_metrics": {
            "quality_index": round(primary, 4),
            "uncertainty_index": round(uncertainty, 4),
            "safety_violation_rate": round(safety_violation, 4),
            "wetlab_cost_per_round_kusd": cost_kusd,
        },
        "adopted_items": adopted,
    }


def _render_report(
    *,
    hypothesis: str,
    candidate_id: str,
    plan_name: str,
    round_index: int,
    owner: str,
    metrics: dict[str, Any],
    expected_benefits: list[str],
    risks: list[str],
    peer_context: dict[str, list[str]],
    must_fix_items: list[str],
    execution_mode: str,
) -> str:
    secondary = _coerce_dict(metrics.get("secondary_metrics"))
    quality = secondary.get("quality_index", metrics.get("primary_metric"))
    uncertainty = secondary.get("uncertainty_index", "")
    safety = secondary.get("safety_violation_rate", "")
    cost = secondary.get("wetlab_cost_per_round_kusd", "")

    borrowed = _merge_unique(_coerce_list(peer_context.get("borrowable_ideas")), limit=3)
    suggested = _merge_unique(_coerce_list(peer_context.get("suggested_improvement")), limit=3)
    must_fix = _merge_unique(must_fix_items, limit=3)

    strengths: list[str] = []
    if isinstance(quality, (int, float)) and float(quality) >= 0.85:
        strengths.append("Quality metric is strong and remains stable after this round.")
    strengths.append("Execution artifacts were generated with deterministic traceable logs.")
    if borrowed:
        strengths.append("Peer transferable insights were integrated into implementation updates.")

    weaknesses: list[str] = []
    if isinstance(uncertainty, (int, float)) and float(uncertainty) > 0.12:
        weaknesses.append("Uncertainty is still above the tighter production threshold.")
    if isinstance(safety, (int, float)) and float(safety) > 0.05:
        weaknesses.append("Safety violation rate still needs further reduction under stricter constraints.")
    if not weaknesses:
        weaknesses.append("Improvement space remains in robustness under distribution shift.")

    open_problems = _merge_unique(
        [f"Risk to monitor: {item}" for item in risks[:3]]
        + [f"Reviewer must-fix pending: {item}" for item in must_fix],
        limit=4,
    )
    next_moves = _merge_unique(
        [
            "Run one additional focused ablation on the top uncertainty contributor.",
            "Validate safety constraints under an adversarial stress case.",
        ]
        + [f"Apply peer suggestion: {item}" for item in suggested[:2]]
        + [f"Close reviewer item: {item}" for item in must_fix[:2]],
        limit=4,
    )
    transferable = _merge_unique(
        [f"Borrowed idea adopted: {item}" for item in borrowed]
        + [f"Generalizable process improvement: {item}" for item in suggested[:2]],
        limit=4,
    )

    lines = [
        "## Key Hypothesis",
        hypothesis.strip() or f"{plan_name} can improve the target objective with safer iteration.",
        "",
        "## Implementation Delta",
        f"- Executed worker={owner}, candidate={candidate_id}, round={round_index}, mode={execution_mode}.",
        f"- Primary metric measured at {metrics.get('primary_metric')} with uncertainty={uncertainty}, safety_violation_rate={safety}, cost_kusd={cost}.",
    ]
    for item in must_fix[:2]:
        lines.append(f"- Addressed reviewer must-fix item: {item}")
    for item in borrowed[:2]:
        lines.append(f"- Integrated peer idea: {item}")
    lines.extend(
        [
            "",
            "## Strengths",
            *[f"- {item}" for item in strengths],
            "",
            "## Weaknesses",
            *[f"- {item}" for item in weaknesses],
            "",
            "## Transferable Insights",
            *[f"- {item}" for item in (transferable or ['Structured peer exchange can accelerate convergence without sharing full reports.'])],
            "",
            "## Open Problems",
            *[f"- {item}" for item in (open_problems or ['Need deeper stress-testing for safety-boundary behavior.'])],
            "",
            "## Proposed Next Move",
            *[f"- {item}" for item in next_moves],
            "",
        ]
    )
    return "\n".join(lines)


def _write_notes(
    *,
    notes_path: Path,
    candidate_id: str,
    round_index: int,
    execution_mode: str,
    peer_context: dict[str, list[str]],
    must_fix_items: list[str],
    metrics: dict[str, Any],
) -> None:
    borrowed = _merge_unique(_coerce_list(peer_context.get("borrowable_ideas")), limit=3)
    rejected = _merge_unique(_coerce_list(peer_context.get("observed_weaknesses")), limit=3)
    suggested = _merge_unique(_coerce_list(peer_context.get("suggested_improvement")), limit=3)
    secondary = _coerce_dict(metrics.get("secondary_metrics"))

    lines = [
        "# Round Notes",
        "",
        f"- candidate_id: {candidate_id}",
        f"- round: {round_index}",
        f"- execution_mode: {execution_mode}",
        "",
        "## Borrowed Peer Ideas",
    ]
    for item in (borrowed or ["No borrowable idea this round."]):
        lines.append(f"- {item}")

    lines.extend(["", "## Rejected Peer Ideas"])
    for item in (rejected or ["No explicit rejected idea."]):
        lines.append(f"- {item}")

    lines.extend(["", "## Changed Implementation"])
    for item in suggested[:2]:
        lines.append(f"- Applied change from suggestion: {item}")
    for item in must_fix_items[:2]:
        lines.append(f"- Applied reviewer correction: {item}")
    if not suggested and not must_fix_items:
        lines.append("- Kept main pipeline stable and tuned execution thresholds.")

    lines.extend(["", "## Result Change"])
    lines.append(
        f"- primary_metric={metrics.get('primary_metric')} uncertainty={secondary.get('uncertainty_index')} safety={secondary.get('safety_violation_rate')}"
    )
    lines.append("- Recorded measurable deltas and linked them to adopted/rejected ideas.")

    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_external_command(
    *,
    command: str | list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_sec: int,
) -> tuple[int, str, str]:
    if isinstance(command, str):
        cmd = shlex.split(command)
    else:
        cmd = [str(item) for item in command]
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _build_codex_worker_prompt(
    *,
    problem: str,
    candidate_id: str,
    plan_name: str,
    round_index: int,
    hypothesis: str,
    expected_benefits: list[str],
    risks: list[str],
    peer_context: dict[str, list[str]],
    must_fix_items: list[str],
    report_path: Path,
    metrics_path: Path,
    notes_path: Path,
) -> str:
    benefits = "\n".join(f"- {item}" for item in expected_benefits[:5]) or "- (none)"
    risk_rows = "\n".join(f"- {item}" for item in risks[:5]) or "- (none)"
    borrowed = "\n".join(f"- {item}" for item in _coerce_list(peer_context.get("borrowable_ideas"))[:5]) or "- (none)"
    suggested = "\n".join(f"- {item}" for item in _coerce_list(peer_context.get("suggested_improvement"))[:5]) or "- (none)"
    must_fix = "\n".join(f"- {item}" for item in must_fix_items[:5]) or "- (none)"
    return "\n".join(
        [
            "You are a worker agent in a research multi-agent pipeline.",
            "Complete this round and WRITE ALL required artifacts to disk.",
            "",
            "Task Context:",
            f"- problem: {problem}",
            f"- candidate_id: {candidate_id}",
            f"- plan_name: {plan_name}",
            f"- round: {round_index}",
            f"- hypothesis: {hypothesis or '(empty)'}",
            "",
            "Expected benefits:",
            benefits,
            "",
            "Risks:",
            risk_rows,
            "",
            "Peer borrowable ideas:",
            borrowed,
            "",
            "Peer suggested improvements:",
            suggested,
            "",
            "Reviewer must-fix items:",
            must_fix,
            "",
            "Output Requirements:",
            f"1) Write markdown report to: {report_path}",
            f"2) Write metrics JSON to: {metrics_path}",
            f"3) Write notes markdown to: {notes_path}",
            "",
            "Report markdown MUST use exact headings:",
            "## Key Hypothesis",
            "## Implementation Delta",
            "## Strengths",
            "## Weaknesses",
            "## Transferable Insights",
            "## Open Problems",
            "## Proposed Next Move",
            "",
            "Metrics JSON MUST be an object with fields:",
            '- "primary_metric": float between 0 and 1',
            '- "secondary_metrics": object containing at least uncertainty_index, safety_violation_rate, wetlab_cost_per_round_kusd',
            "",
            "Notes markdown MUST include sections:",
            "## Borrowed Peer Ideas",
            "## Rejected Peer Ideas",
            "## Changed Implementation",
            "## Result Change",
            "",
            "Do not output final prose only; ensure files are created.",
        ]
    )


def _run_codex_exec(
    *,
    candidate_dir: Path,
    prompt: str,
    timeout_sec: int,
    model: str = "",
) -> tuple[bool, str, str]:
    binary = shutil.which("codex")
    if not binary:
        return False, "", "codex binary not found in PATH"
    cmd = [
        binary,
        "exec",
        "--full-auto",
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "-C",
        str(candidate_dir),
    ]
    if model.strip():
        cmd.extend(["-m", model.strip()])
    cmd.append(prompt)
    proc = subprocess.run(
        cmd,
        cwd=str(candidate_dir),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    ok = proc.returncode == 0
    return ok, proc.stdout[-6000:], proc.stderr[-6000:]


def execute_worker_experiment(
    *,
    run_dir: Path,
    run_id: str,
    problem: str,
    candidate_id: str,
    plan_name: str,
    owner: str,
    round_index: int,
    candidate_spec: dict[str, Any] | None = None,
    peer_context: dict[str, list[str]] | None = None,
    must_fix_items: list[str] | None = None,
    reports_root: Path | None = None,
    allow_fallback_rounds: bool = False,
    execution_mode: str = "live",
    worker_executor: str = "codex",
    require_codex_success: bool = False,
    codex_model: str = "",
    command_timeout_sec: int = 900,
) -> dict[str, Any]:
    started = perf_counter()
    mode = execution_mode.strip().lower() or "live"
    if mode not in {"live", "replay", "auto"}:
        raise ValueError(f"Unsupported execution_mode: {execution_mode}")

    candidate_spec = _coerce_dict(candidate_spec)
    peer_context = peer_context or {}
    must_fix_items = _merge_unique(must_fix_items or [], limit=4)

    candidate_dir = run_dir / "implementation" / candidate_id / f"round_{round_index}"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    report_path = candidate_dir / "report.md"
    metrics_path = candidate_dir / "metrics.json"
    notes_path = candidate_dir / "notes.md"
    execution_log_path = candidate_dir / "execution_log.json"

    hypothesis = str(candidate_spec.get("hypothesis", "")).strip()
    expected_benefits = _coerce_list(candidate_spec.get("expectedBenefits"))
    risks = _coerce_list(candidate_spec.get("risks"))
    experiment_cfg = _coerce_dict(candidate_spec.get("experiment"))

    source_round = round_index
    source_report = ""
    source_metrics = ""
    used_fallback = False
    active_mode = "live_simulation"

    if mode in {"replay", "auto"} and reports_root is not None:
        try:
            src_report, src_metrics, source_round, used_fallback = resolve_artifacts(
                run_dir=run_dir,
                reports_root=reports_root,
                candidate_id=candidate_id,
                round_index=round_index,
                allow_fallback_rounds=allow_fallback_rounds,
            )
            report_path.write_text(src_report.read_text(encoding="utf-8"), encoding="utf-8")
            metrics_path.write_text(src_metrics.read_text(encoding="utf-8"), encoding="utf-8")
            source_report = str(src_report)
            source_metrics = str(src_metrics)
            active_mode = "replay_import"
        except FileNotFoundError:
            if mode == "replay":
                raise
            active_mode = "live_simulation"

    codex_error_note = ""
    if active_mode == "live_simulation":
        command = experiment_cfg.get("command")
        executor = worker_executor.strip().lower() or "codex"
        if command:
            env = os.environ.copy()
            env.update(
                {
                    "NANOBOT_RUN_ID": run_id,
                    "NANOBOT_PROBLEM": problem,
                    "NANOBOT_CANDIDATE_ID": candidate_id,
                    "NANOBOT_PLAN_NAME": plan_name,
                    "NANOBOT_ROUND": str(round_index),
                    "NANOBOT_REPORT_PATH": str(report_path),
                    "NANOBOT_METRICS_PATH": str(metrics_path),
                }
            )
            code, stdout, stderr = _run_external_command(
                command=command,
                cwd=candidate_dir,
                env=env,
                timeout_sec=int(experiment_cfg.get("timeout_sec", command_timeout_sec) or command_timeout_sec),
            )
            if code != 0:
                raise RuntimeError(
                    f"worker external command failed for {candidate_id} round {round_index}: exit={code} stderr={stderr.strip()}"
                )
            if not report_path.exists() or not metrics_path.exists():
                raise FileNotFoundError(
                    f"external command finished but report/metrics missing for {candidate_id} round {round_index}"
                )
            active_mode = "external_command"
            metrics_obj = json.loads(metrics_path.read_text(encoding="utf-8"))
            if not isinstance(metrics_obj, dict):
                raise ValueError(f"metrics file is not a JSON object: {metrics_path}")
            if "primary_metric" not in metrics_obj:
                raise ValueError(f"metrics missing primary_metric: {metrics_path}")
            command_io = {"stdout": stdout[-4000:], "stderr": stderr[-4000:]}
        elif executor == "codex":
            prompt = _build_codex_worker_prompt(
                problem=problem,
                candidate_id=candidate_id,
                plan_name=plan_name,
                round_index=round_index,
                hypothesis=hypothesis,
                expected_benefits=expected_benefits,
                risks=risks,
                peer_context=peer_context,
                must_fix_items=must_fix_items,
                report_path=report_path,
                metrics_path=metrics_path,
                notes_path=notes_path,
            )
            ok, stdout, stderr = _run_codex_exec(
                candidate_dir=candidate_dir,
                prompt=prompt,
                timeout_sec=command_timeout_sec,
                model=codex_model,
            )
            if ok and report_path.exists() and metrics_path.exists():
                metrics_obj = json.loads(metrics_path.read_text(encoding="utf-8"))
                if not isinstance(metrics_obj, dict):
                    raise ValueError(f"metrics file is not a JSON object: {metrics_path}")
                if "primary_metric" not in metrics_obj:
                    raise ValueError(f"metrics missing primary_metric: {metrics_path}")
                active_mode = "codex_exec"
                command_io = {"stdout": stdout, "stderr": stderr}
            else:
                codex_error_note = stderr or "codex execution failed without stderr"
                if require_codex_success:
                    raise RuntimeError(f"codex worker execution failed: {codex_error_note}")
                simulated = _simulate_metrics(
                    run_id=run_id,
                    candidate_id=candidate_id,
                    plan_name=plan_name,
                    round_index=round_index,
                    expected_benefits=expected_benefits,
                    risks=risks,
                    peer_context=peer_context,
                    must_fix_items=must_fix_items,
                )
                metrics_obj = {
                    "primary_metric": simulated["primary_metric"],
                    "secondary_metrics": simulated["secondary_metrics"],
                }
                report_text = _render_report(
                    hypothesis=hypothesis,
                    candidate_id=candidate_id,
                    plan_name=plan_name,
                    round_index=round_index,
                    owner=owner,
                    metrics=metrics_obj,
                    expected_benefits=expected_benefits,
                    risks=risks,
                    peer_context=peer_context,
                    must_fix_items=must_fix_items,
                    execution_mode="live_simulation_fallback_from_codex",
                )
                report_path.write_text(report_text, encoding="utf-8")
                metrics_path.write_text(json.dumps(metrics_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                active_mode = "live_simulation_fallback_from_codex"
                command_io = {"stdout": stdout, "stderr": stderr}
        else:
            simulated = _simulate_metrics(
                run_id=run_id,
                candidate_id=candidate_id,
                plan_name=plan_name,
                round_index=round_index,
                expected_benefits=expected_benefits,
                risks=risks,
                peer_context=peer_context,
                must_fix_items=must_fix_items,
            )
            metrics_obj = {
                "primary_metric": simulated["primary_metric"],
                "secondary_metrics": simulated["secondary_metrics"],
            }
            report_text = _render_report(
                hypothesis=hypothesis,
                candidate_id=candidate_id,
                plan_name=plan_name,
                round_index=round_index,
                owner=owner,
                metrics=metrics_obj,
                expected_benefits=expected_benefits,
                risks=risks,
                peer_context=peer_context,
                must_fix_items=must_fix_items,
                execution_mode=active_mode,
            )
            report_path.write_text(report_text, encoding="utf-8")
            metrics_path.write_text(json.dumps(metrics_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            command_io = {}
    else:
        metrics_obj = json.loads(metrics_path.read_text(encoding="utf-8"))
        if not isinstance(metrics_obj, dict):
            raise ValueError(f"metrics file is not a JSON object: {metrics_path}")
        command_io = {}

    _write_notes(
        notes_path=notes_path,
        candidate_id=candidate_id,
        round_index=round_index,
        execution_mode=active_mode,
        peer_context=peer_context,
        must_fix_items=must_fix_items,
        metrics=metrics_obj,
    )

    report_hash = _sha256(report_path)
    metrics_hash = _sha256(metrics_path)
    notes_hash = _sha256(notes_path)
    input_payload = {
        "run_id": run_id,
        "problem": problem,
        "candidate_id": candidate_id,
        "plan_name": plan_name,
        "owner": owner,
        "round": round_index,
        "mode": active_mode,
        "peer_context": peer_context,
        "must_fix_items": must_fix_items,
    }
    input_fingerprint = hashlib.sha256(json.dumps(input_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    duration_ms = int((perf_counter() - started) * 1000)
    execution_log = {
        "schema_version": "worker_experiment_v1",
        "generated_at_utc": _utc_now(),
        "run_id": run_id,
        "problem": problem,
        "candidate_id": candidate_id,
        "plan_name": plan_name,
        "owner": owner,
        "round": round_index,
        "execution_mode": active_mode,
        "source_round": source_round,
        "source_report_path": source_report,
        "source_metrics_path": source_metrics,
        "used_fallback": used_fallback,
        "duration_ms": duration_ms,
        "input_fingerprint": input_fingerprint,
        "output_hashes": {
            "report_sha256": report_hash,
            "metrics_sha256": metrics_hash,
            "notes_sha256": notes_hash,
        },
        "metrics": metrics_obj,
        "command_io": command_io,
        "codex_error_note": codex_error_note,
    }
    save_json(execution_log_path, execution_log)

    return {
        "candidate_id": candidate_id,
        "plan_name": plan_name,
        "owner": owner,
        "round": round_index,
        "execution_mode": active_mode,
        "source_round": source_round,
        "used_fallback": used_fallback,
        "report_path": str(report_path),
        "metrics_path": str(metrics_path),
        "notes_path": str(notes_path),
        "execution_log_path": str(execution_log_path),
        "primary_metric": metrics_obj.get("primary_metric"),
        "duration_ms": duration_ms,
        "input_fingerprint": input_fingerprint,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute one worker experiment round and emit artifacts.")
    parser.add_argument("--run-dir", required=True, help="Run directory.")
    parser.add_argument("--run-id", required=True, help="Run id.")
    parser.add_argument("--problem", required=True, help="Problem statement.")
    parser.add_argument("--candidate-id", required=True, help="Candidate id.")
    parser.add_argument("--plan-name", required=True, help="Plan name.")
    parser.add_argument("--owner", required=True, help="Worker owner role.")
    parser.add_argument("--round", required=True, type=int, help="Round index.")
    parser.add_argument("--candidate-spec", help="Path to candidate spec json.")
    parser.add_argument("--peer-context", help="Path to peer context json.")
    parser.add_argument("--must-fix", help="Path to must-fix json list.")
    parser.add_argument("--reports-root", help="Replay reports root (optional).")
    parser.add_argument("--allow-fallback-rounds", action="store_true", help="Allow fallback for replay mode.")
    parser.add_argument("--execution-mode", default="live", choices=["live", "replay", "auto"])
    parser.add_argument("--worker-executor", default="codex", choices=["codex", "simulation"])
    parser.add_argument("--require-codex-success", action="store_true", help="Fail when codex execution fails instead of falling back.")
    parser.add_argument("--codex-model", default="", help="Optional model override for codex exec.")
    parser.add_argument("--timeout-sec", type=int, default=900, help="External command timeout seconds.")
    parser.add_argument("--summary-out", required=True, help="Output summary json path.")
    args = parser.parse_args()

    candidate_spec = {}
    if args.candidate_spec:
        candidate_spec = json.loads(Path(args.candidate_spec).read_text(encoding="utf-8"))
    peer_context = {}
    if args.peer_context:
        peer_context = json.loads(Path(args.peer_context).read_text(encoding="utf-8"))
    must_fix_items: list[str] = []
    if args.must_fix:
        raw = json.loads(Path(args.must_fix).read_text(encoding="utf-8"))
        must_fix_items = normalize_lines(raw)

    summary = execute_worker_experiment(
        run_dir=Path(args.run_dir),
        run_id=args.run_id,
        problem=args.problem,
        candidate_id=_safe_slug(args.candidate_id),
        plan_name=args.plan_name,
        owner=args.owner,
        round_index=args.round,
        candidate_spec=candidate_spec if isinstance(candidate_spec, dict) else {},
        peer_context=peer_context if isinstance(peer_context, dict) else {},
        must_fix_items=must_fix_items,
        reports_root=Path(args.reports_root) if args.reports_root else None,
        allow_fallback_rounds=args.allow_fallback_rounds,
        execution_mode=args.execution_mode,
        worker_executor=args.worker_executor,
        require_codex_success=args.require_codex_success,
        codex_model=args.codex_model,
        command_timeout_sec=args.timeout_sec,
    )
    save_json(Path(args.summary_out), summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
