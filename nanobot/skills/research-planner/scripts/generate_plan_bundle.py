from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def _search_context(problem: str, max_results: int) -> list[dict[str, str]]:
    # Search is best-effort: the script still works offline.
    enable_search = os.getenv("NANOBOT_ENABLE_DDGS_SEARCH", "").strip().lower() in {"1", "true", "yes", "on"}
    if not enable_search:
        return []
    try:
        from ddgs import DDGS  # type: ignore
    except Exception:
        return []

    query = f"{problem} research benchmark baseline ablation"
    rows: list[dict[str, str]] = []
    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                if not isinstance(item, dict):
                    continue
                rows.append(
                    {
                        "title": str(item.get("title", "")).strip(),
                        "href": str(item.get("href", "")).strip(),
                        "body": str(item.get("body", "")).strip(),
                    }
                )
    except Exception:
        return []
    return rows


def _strategy_bank(problem: str) -> list[dict[str, Any]]:
    p = problem.lower()
    cost_bias = any(key in p for key in ("cost", "latency", "budget", "efficiency"))
    quality_bias = any(key in p for key in ("quality", "accuracy", "performance", "sota", "robust"))

    bank = [
        {
            "candidateId": "candidate_01",
            "name": "Retrieval-first planning",
            "hypothesis": "Grounding decomposition with retrieval improves plan quality.",
            "implementationSpec": "Retrieve related work before plan decomposition and evidence-check each subgoal.",
            "expectedBenefits": ["better grounding", "fewer weak plan branches"],
            "risks": ["higher latency", "retrieval cost"],
        },
        {
            "candidateId": "candidate_02",
            "name": "Ranking-first planning",
            "hypothesis": "A cheap ranking heuristic can keep quality while reducing cost.",
            "implementationSpec": "Generate multiple plan drafts and rank by a lightweight scorer before execution.",
            "expectedBenefits": ["lower cost", "faster iteration"],
            "risks": ["weaker evidence grounding", "false positives"],
        },
        {
            "candidateId": "candidate_03",
            "name": "Critique-loop planning",
            "hypothesis": "Self-critique with explicit failure checks improves robustness.",
            "implementationSpec": "Add a structured critique pass for assumptions, baselines, and reproducibility gaps.",
            "expectedBenefits": ["stronger robustness", "clearer failure analysis"],
            "risks": ["longer planning time", "more moving parts"],
        },
        {
            "candidateId": "candidate_04",
            "name": "Debate-fusion planning",
            "hypothesis": "Cross-candidate debate exposes blind spots and yields better hybrid plans.",
            "implementationSpec": "Run pairwise candidate critique and synthesize a hybrid using transferable insights.",
            "expectedBenefits": ["better exploration", "higher chance of fusion gains"],
            "risks": ["coordination overhead", "noise in discussion"],
        },
        {
            "candidateId": "candidate_05",
            "name": "Adaptive-budget planning",
            "hypothesis": "Dynamic budget allocation by uncertainty gives better cost-quality tradeoff.",
            "implementationSpec": "Allocate retrieval/compute budget based on uncertainty and expected information gain.",
            "expectedBenefits": ["cost control", "focus on high-uncertainty subgoals"],
            "risks": ["budget policy instability", "harder tuning"],
        },
    ]

    if cost_bias and not quality_bias:
        # Put lower-cost strategies first.
        order = [1, 4, 2, 0, 3]
        bank = [bank[i] for i in order]
    elif quality_bias and not cost_bias:
        order = [0, 2, 3, 1, 4]
        bank = [bank[i] for i in order]

    # Re-assign stable candidate ids after ordering.
    for idx, item in enumerate(bank, start=1):
        item["candidateId"] = f"candidate_{idx:02d}"
    return bank


def _acceptance_spec() -> dict[str, Any]:
    return {
        "hard_requirements": [
            "shared board can be initialized",
            "worker digests can be published",
            "peer feedback can be merged",
            "agenda can be generated from board findings",
            "review feedback can be generated with tool evidence",
            "final conclusion artifacts can be generated",
            "main experiment can be reproduced",
            "report uses actual measured metrics",
            "worker notes record adopted and rejected peer ideas",
        ],
        "soft_requirements": [
            "global findings identify strengths and failures",
            "worker actions reflect peer feedback",
            "final recommendation includes next actions",
        ],
        "review_checks": [
            {"name": "validate_inbox_envelope", "tool": "exec", "required": True},
            {"name": "validate_candidate_coverage", "tool": "exec", "required": True},
            {"name": "validate_execution_evidence", "tool": "exec", "required": True},
            {"name": "verify_report_metric_consistency", "tool": "exec", "required": True},
            {"name": "require_worker_notes_evidence", "tool": "exec", "required": True},
        ],
    }


def _write_json(path: Path, payload: Any) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_plan_brief(path: Path, problem: str, candidates: list[dict[str, Any]], refs: list[dict[str, str]]) -> None:
    lines: list[str] = []
    lines.append("# Plan Brief")
    lines.append("")
    lines.append(f"- generated_at: {datetime.utcnow().isoformat()}Z")
    lines.append(f"- problem: {problem}")
    lines.append(f"- candidate_count: {len(candidates)}")
    lines.append("")
    lines.append("## Candidate Overview")
    lines.append("")
    for item in candidates:
        lines.append(f"### {item['candidateId']} | {item['name']}")
        lines.append("")
        lines.append(f"- hypothesis: {item['hypothesis']}")
        lines.append(f"- implementation: {item['implementationSpec']}")
        lines.append(f"- expected_benefits: {', '.join(item['expectedBenefits'])}")
        lines.append(f"- risks: {', '.join(item['risks'])}")
        lines.append("")

    lines.append("## Search Evidence (Best Effort)")
    lines.append("")
    if not refs:
        lines.append("- No external search evidence captured (offline mode or no results).")
    else:
        for idx, row in enumerate(refs, start=1):
            title = row.get("title", "") or "(untitled)"
            href = row.get("href", "")
            body = row.get("body", "")
            lines.append(f"{idx}. {title}")
            if href:
                lines.append(f"   - link: {href}")
            if body:
                lines.append(f"   - note: {body[:220]}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_plan_bundle(
    problem: str,
    output_dir: Path,
    candidate_count: int = 3,
    search_results: int = 8,
) -> dict[str, Any]:
    if candidate_count < 3 or candidate_count > 5:
        raise ValueError("candidate_count must be between 3 and 5.")

    refs = _search_context(problem, max_results=search_results)
    bank = _strategy_bank(problem)
    candidates = bank[:candidate_count]
    acceptance = _acceptance_spec()

    plan_dir = output_dir / "plan"
    candidates_path = plan_dir / "candidates.json"
    acceptance_path = plan_dir / "acceptance_spec.json"
    plan_brief_path = plan_dir / "plan_brief.md"

    _write_json(candidates_path, candidates)
    _write_json(acceptance_path, acceptance)
    _write_plan_brief(plan_brief_path, problem, candidates, refs)

    return {
        "problem": problem,
        "plan_dir": str(plan_dir),
        "candidates_path": str(candidates_path),
        "acceptance_path": str(acceptance_path),
        "plan_brief_path": str(plan_brief_path),
        "candidate_count": len(candidates),
        "search_refs_count": len(refs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate planner outputs for a research run.")
    parser.add_argument("--problem", required=True, help="Research problem statement.")
    parser.add_argument("--output-dir", required=True, help="Run directory where plan/* files are written.")
    parser.add_argument("--candidate-count", type=int, default=3, help="Number of candidates (3-5).")
    parser.add_argument("--search-results", type=int, default=8, help="Max number of search snippets.")
    args = parser.parse_args()

    summary = generate_plan_bundle(
        problem=args.problem,
        output_dir=Path(args.output_dir),
        candidate_count=args.candidate_count,
        search_results=args.search_results,
    )
    _write_json(Path(args.output_dir) / "plan" / "plan_bundle_summary.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
