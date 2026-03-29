from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_artifacts(
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
            "Provide files for this round or enable fallback rounds."
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
        raise FileNotFoundError(f"No report/metrics pair found for {candidate_id}.")

    idx, report, metrics = sorted(candidates, key=lambda row: row[0])[-1]
    return report, metrics, idx, True


def ensure_notes_file(
    run_dir: Path,
    candidate_id: str,
    round_index: int,
    used_round: int,
    used_fallback: bool,
) -> Path:
    notes_path = run_dir / "implementation" / candidate_id / f"round_{round_index}" / "notes.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    if notes_path.exists():
        return notes_path

    fallback_note = "true" if used_fallback else "false"
    lines = [
        "# Round Notes",
        "",
        f"- candidate_id: {candidate_id}",
        f"- round: {round_index}",
        f"- source_round: {used_round}",
        f"- fallback_used: {fallback_note}",
        "",
        "## Borrowed Peer Ideas",
        "- (pending peer analysis)",
        "",
        "## Rejected Peer Ideas",
        "- (pending peer analysis)",
        "",
        "## Changed Implementation",
        "- (summarize code or experiment changes)",
        "",
        "## Result Change",
        "- (describe whether metrics improved)",
        "",
    ]
    notes_path.write_text("\n".join(lines), encoding="utf-8")
    return notes_path


def normalize_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    output.append(text)
        return output
    return []


def build_feedback_from_entry(entry: dict[str, Any]) -> dict[str, list[str]]:
    strengths = normalize_lines(entry.get("strengths"))
    weaknesses = normalize_lines(entry.get("weaknesses"))
    open_problems = normalize_lines(entry.get("open_problems"))
    insights = normalize_lines(entry.get("transferable_insights"))
    next_moves = normalize_lines(entry.get("proposed_next_move"))

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
