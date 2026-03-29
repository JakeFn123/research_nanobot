from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


WORKER_KEYS = {
    "owner",
    "plan_name",
    "round",
    "status",
    "key_hypothesis",
    "implementation_delta",
    "core_metrics",
    "strengths",
    "weaknesses",
    "transferable_insights",
    "open_problems",
    "proposed_next_move",
    "private_report_path",
}

FEEDBACK_KEYS = {
    "observed_strengths",
    "observed_weaknesses",
    "borrowable_ideas",
    "suggested_improvement",
}


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def normalize_secondary_metrics(metrics: Any) -> dict[str, Any]:
    if isinstance(metrics, dict):
        return metrics
    return {}


def coerce_primary_metric(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_candidates(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("candidates"), list):
        return [item for item in payload["candidates"] if isinstance(item, dict)]
    raise ValueError("Candidates payload must be a list or {'candidates': [...]} structure.")


def incoming_feedback(board: dict[str, Any], candidate_id: str) -> list[dict[str, Any]]:
    feedback = board.get("peer_feedback", {})
    if not isinstance(feedback, dict):
        return []
    suffix = f"_on_{candidate_id}"
    return [
        item for key, item in feedback.items()
        if key.endswith(suffix) and isinstance(item, dict)
    ]


def top_phrases(groups: list[list[str]], limit: int = 5) -> list[str]:
    counter: Counter[str] = Counter()
    original: dict[str, str] = {}
    for group in groups:
        for item in group:
            normalized = item.strip().lower()
            if not normalized:
                continue
            counter[normalized] += 1
            original.setdefault(normalized, item.strip())
    return [original[key] for key, _ in counter.most_common(limit)]


def praise_score(board: dict[str, Any], candidate_id: str) -> int:
    return sum(
        len(normalize_lines(item.get("observed_strengths")))
        for item in incoming_feedback(board, candidate_id)
    )


def concern_score(board: dict[str, Any], candidate_id: str) -> int:
    return sum(
        len(normalize_lines(item.get("observed_weaknesses")))
        for item in incoming_feedback(board, candidate_id)
    )


def validate_worker_entry(entry: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(entry) - WORKER_KEYS)
    if unknown:
        raise ValueError(f"Unknown worker entry keys: {', '.join(unknown)}")
    metrics = entry.get("core_metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    return {
        "owner": str(entry.get("owner", "")).strip(),
        "plan_name": str(entry.get("plan_name", "")).strip(),
        "round": int(entry.get("round", 0) or 0),
        "status": str(entry.get("status", "active")).strip() or "active",
        "key_hypothesis": str(entry.get("key_hypothesis", "")).strip(),
        "implementation_delta": normalize_lines(entry.get("implementation_delta")),
        "core_metrics": {
            "primary_metric": coerce_primary_metric(
                metrics.get("primary_metric", metrics.get("primary"))
            ),
            "secondary_metrics": normalize_secondary_metrics(
                metrics.get("secondary_metrics", metrics.get("secondary"))
            ),
        },
        "strengths": normalize_lines(entry.get("strengths")),
        "weaknesses": normalize_lines(entry.get("weaknesses")),
        "transferable_insights": normalize_lines(entry.get("transferable_insights")),
        "open_problems": normalize_lines(entry.get("open_problems")),
        "proposed_next_move": normalize_lines(entry.get("proposed_next_move")),
        "private_report_path": str(entry.get("private_report_path", "")).strip(),
    }


def validate_feedback_entry(entry: dict[str, Any]) -> dict[str, list[str]]:
    unknown = sorted(set(entry) - FEEDBACK_KEYS)
    if unknown:
        raise ValueError(f"Unknown feedback entry keys: {', '.join(unknown)}")
    return {
        "observed_strengths": normalize_lines(entry.get("observed_strengths")),
        "observed_weaknesses": normalize_lines(entry.get("observed_weaknesses")),
        "borrowable_ideas": normalize_lines(entry.get("borrowable_ideas")),
        "suggested_improvement": normalize_lines(entry.get("suggested_improvement")),
    }


def ensure_board_shape(board: dict[str, Any]) -> dict[str, Any]:
    board.setdefault("run_id", "")
    board.setdefault("problem", "")
    board.setdefault("acceptance_spec_path", "")
    board.setdefault("round_index", 0)
    board.setdefault("workers", {})
    board.setdefault("worker_ownership", {})
    board.setdefault("peer_feedback", {})
    board.setdefault("global_findings", {})
    if not isinstance(board["workers"], dict):
        raise ValueError("'workers' must be a JSON object.")
    if not isinstance(board["worker_ownership"], dict):
        raise ValueError("'worker_ownership' must be a JSON object.")
    if not isinstance(board["peer_feedback"], dict):
        raise ValueError("'peer_feedback' must be a JSON object.")
    if not isinstance(board["global_findings"], dict):
        raise ValueError("'global_findings' must be a JSON object.")
    for candidate_id, entry in board["workers"].items():
        if not isinstance(candidate_id, str) or not isinstance(entry, dict):
            continue
        owner = str(entry.get("owner", "")).strip()
        if owner and candidate_id not in board["worker_ownership"]:
            board["worker_ownership"][candidate_id] = owner
    return board
