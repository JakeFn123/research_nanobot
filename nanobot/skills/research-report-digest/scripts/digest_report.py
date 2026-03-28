from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


SECTION_KEYS = {
    "key hypothesis": "key_hypothesis",
    "implementation delta": "implementation_delta",
    "strengths": "strengths",
    "weaknesses": "weaknesses",
    "transferable insights": "transferable_insights",
    "open problems": "open_problems",
    "proposed next move": "proposed_next_move",
}


def _read_json(path: Path) -> Any:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _extract_sections(report_text: str) -> dict[str, list[str] | str]:
    current: str | None = None
    bucket: dict[str, list[str]] = {value: [] for value in SECTION_KEYS.values()}
    hypothesis_lines: list[str] = []

    for raw_line in report_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("#"):
            heading = line.lstrip("#").strip().lower()
            current = SECTION_KEYS.get(heading)
            continue

        if current is None:
            continue

        text = line.strip()
        if not text:
            continue
        if text.startswith("- "):
            text = text[2:].strip()
        elif text.startswith("* "):
            text = text[2:].strip()

        if not text:
            continue

        if current == "key_hypothesis":
            hypothesis_lines.append(text)
        else:
            bucket[current].append(text)

    return {
        "key_hypothesis": " ".join(hypothesis_lines).strip(),
        "implementation_delta": bucket["implementation_delta"],
        "strengths": bucket["strengths"],
        "weaknesses": bucket["weaknesses"],
        "transferable_insights": bucket["transferable_insights"],
        "open_problems": bucket["open_problems"],
        "proposed_next_move": bucket["proposed_next_move"],
    }


def digest_report(
    report_path: Path,
    metrics_path: Path,
    candidate_id: str,
    plan_name: str,
    round_index: int,
    owner: str,
    output_path: Path,
    status: str = "active",
) -> dict[str, Any]:
    report_text = report_path.read_text(encoding="utf-8")
    parsed = _extract_sections(report_text)
    metrics = _read_json(metrics_path)

    primary_metric = metrics.get("primary_metric", metrics.get("primary"))
    secondary_metrics = metrics.get("secondary_metrics", metrics.get("secondary", {}))
    if not isinstance(secondary_metrics, dict):
        secondary_metrics = {}

    digest = {
        "owner": owner,
        "plan_name": plan_name,
        "round": round_index,
        "status": status,
        "key_hypothesis": parsed["key_hypothesis"],
        "implementation_delta": parsed["implementation_delta"],
        "core_metrics": {
            "primary_metric": primary_metric,
            "secondary_metrics": secondary_metrics,
        },
        "strengths": parsed["strengths"],
        "weaknesses": parsed["weaknesses"],
        "transferable_insights": parsed["transferable_insights"],
        "open_problems": parsed["open_problems"],
        "proposed_next_move": parsed["proposed_next_move"],
        "private_report_path": str(report_path),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    import json

    output_path.write_text(json.dumps(digest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract a structured worker digest from a private report.")
    parser.add_argument("--report", required=True, help="Path to the private report markdown file.")
    parser.add_argument("--metrics", required=True, help="Path to the metrics json file.")
    parser.add_argument("--candidate-id", required=True, help="Candidate identifier.")
    parser.add_argument("--plan-name", required=True, help="Candidate plan name.")
    parser.add_argument("--round", required=True, type=int, help="Round index.")
    parser.add_argument("--owner", default="", help="Worker label.")
    parser.add_argument("--status", default="active", help="Worker status for the digest.")
    parser.add_argument("--output", required=True, help="Path to the digest json output.")
    args = parser.parse_args()
    digest_report(
        report_path=Path(args.report),
        metrics_path=Path(args.metrics),
        candidate_id=args.candidate_id,
        plan_name=args.plan_name,
        round_index=args.round,
        owner=args.owner,
        output_path=Path(args.output),
        status=args.status,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
