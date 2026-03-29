import importlib
import json
import sys
from pathlib import Path

IMPLEMENTER_SCRIPT_DIR = Path("nanobot/skills/research-implementer/scripts").resolve()
if str(IMPLEMENTER_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(IMPLEMENTER_SCRIPT_DIR))

REVIEWER_SCRIPT_DIR = Path("nanobot/skills/research-reviewer/scripts").resolve()
if str(REVIEWER_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(REVIEWER_SCRIPT_DIR))

BLACKBOARD_SCRIPT_DIR = Path("nanobot/skills/research-blackboard/scripts").resolve()
if str(BLACKBOARD_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(BLACKBOARD_SCRIPT_DIR))

inbox_lib = importlib.import_module("inbox_lib")
summarize_round_messages = importlib.import_module("summarize_round_messages")
route_review_feedback = importlib.import_module("route_review_feedback")
review_inbox_run = importlib.import_module("review_inbox_run")
run_inbox_cycle = importlib.import_module("run_inbox_cycle")
research_board_lib = importlib.import_module("research_board_lib")


def test_inbox_send_read_ack_roundtrip(tmp_path: Path) -> None:
    inbox_root = tmp_path / "runtime" / "inbox"

    msg = inbox_lib.send_message(
        inbox_root=inbox_root,
        run_id="run_001",
        round_index=1,
        from_role="worker_01",
        to_role="implementer",
        message_type="worker_round_update",
        correlation_id="task_candidate_01_r1",
        payload={"candidate_id": "candidate_01", "core_metrics": {"primary_metric": 0.8}},
    )

    rows = inbox_lib.read_inbox(inbox_root=inbox_root, role="implementer", limit=10)
    assert len(rows) == 1
    assert rows[0]["id"] == msg["id"]

    inbox_lib.ack_messages(
        inbox_root=inbox_root,
        role="implementer",
        message_ids=[msg["id"]],
        actor="implementer",
        reason="processed",
    )

    rows_after_ack = inbox_lib.read_inbox(inbox_root=inbox_root, role="implementer", limit=10)
    assert rows_after_ack == []


def test_summarize_round_messages_ranks_candidates(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_001"
    inbox_root = run_dir / "runtime" / "inbox"

    inbox_lib.send_message(
        inbox_root=inbox_root,
        run_id="run_001",
        round_index=1,
        from_role="worker_01",
        to_role="implementer",
        message_type="worker_round_update",
        correlation_id="u1",
        payload={
            "candidate_id": "candidate_01",
            "plan_name": "Plan A",
            "core_metrics": {"primary_metric": 0.75},
            "strengths": ["good stability"],
            "weaknesses": ["slow"],
            "open_problems": ["cost"],
        },
    )
    inbox_lib.send_message(
        inbox_root=inbox_root,
        run_id="run_001",
        round_index=1,
        from_role="worker_02",
        to_role="implementer",
        message_type="worker_round_update",
        correlation_id="u2",
        payload={
            "candidate_id": "candidate_02",
            "plan_name": "Plan B",
            "core_metrics": {"primary_metric": 0.83},
            "strengths": ["high quality"],
            "weaknesses": ["latency"],
            "open_problems": [],
        },
    )
    inbox_lib.send_message(
        inbox_root=inbox_root,
        run_id="run_001",
        round_index=1,
        from_role="worker_01",
        to_role="implementer",
        message_type="improvement_proposal",
        correlation_id="p1",
        payload={"suggested_improvement": ["optimize latency"]},
    )

    summary_path = run_dir / "runtime" / "round_summaries" / "round_1.json"
    summary = summarize_round_messages.summarize_round_messages(
        run_dir=run_dir,
        round_index=1,
        output_path=summary_path,
    )

    assert summary_path.exists()
    assert summary["candidate_rank_hint"][0]["candidate_id"] == "candidate_02"
    assert "optimize latency" in summary["improvement_targets"]


def test_route_review_feedback_creates_redo_messages(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_001"
    research_board_lib.save_json(
        run_dir / "plan" / "candidates.json",
        [
            {"candidateId": "candidate_01", "name": "Plan A"},
            {"candidateId": "candidate_02", "name": "Plan B"},
            {"candidateId": "candidate_03", "name": "Plan C"},
        ],
    )
    research_board_lib.save_json(
        run_dir / "review" / "review_feedback.json",
        {
            "approved": False,
            "must_fix": ["candidate_02 should add stronger baseline", "improve evidence quality"],
            "optional_improvements": [],
            "evidence": [],
        },
    )

    output_path = run_dir / "review" / "redo_routing.json"
    payload = route_review_feedback.route_review_feedback(
        run_dir=run_dir,
        review_feedback_path=run_dir / "review" / "review_feedback.json",
        round_index=4,
        output_path=output_path,
    )

    assert output_path.exists()
    assert payload["routed_count"] >= 2
    worker2_inbox = run_dir / "runtime" / "inbox" / "worker_02.jsonl"
    assert worker2_inbox.exists()


def _write_report(path: Path, hypothesis: str, delta: str, strength: str, weakness: str, insight: str, problem: str, next_move: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "## Key Hypothesis",
                hypothesis,
                "",
                "## Implementation Delta",
                f"- {delta}",
                "",
                "## Strengths",
                f"- {strength}",
                "",
                "## Weaknesses",
                f"- {weakness}",
                "",
                "## Transferable Insights",
                f"- {insight}",
                "",
                "## Open Problems",
                f"- {problem}",
                "",
                "## Proposed Next Move",
                f"- {next_move}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_run_inbox_cycle_end_to_end(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    reports_root = tmp_path / "reports"

    candidates = [
        {"candidateId": "candidate_01", "name": "Plan A"},
        {"candidateId": "candidate_02", "name": "Plan B"},
        {"candidateId": "candidate_03", "name": "Plan C"},
    ]
    acceptance = {
        "hard_requirements": [
            "shared board can be initialized",
            "worker digests can be published",
            "peer feedback can be merged",
            "agenda can be generated from board findings",
            "review feedback can be generated with tool evidence",
            "final conclusion artifacts can be generated",
        ],
        "soft_requirements": ["worker actions reflect peer feedback"],
        "review_checks": [{"name": "validate_inbox_envelope", "required": True}],
    }

    candidates_file = tmp_path / "plan" / "candidates.json"
    acceptance_file = tmp_path / "plan" / "acceptance_spec.json"
    research_board_lib.save_json(candidates_file, candidates)
    research_board_lib.save_json(acceptance_file, acceptance)

    for round_idx in (1, 2, 3):
        _write_report(
            reports_root / f"candidate_01_round_{round_idx}_report.md",
            hypothesis="A improves grounding",
            delta=f"A delta {round_idx}",
            strength="stable output",
            weakness="higher latency",
            insight="use staged retrieval",
            problem="cost spikes",
            next_move="reduce retrieval calls",
        )
        _write_report(
            reports_root / f"candidate_02_round_{round_idx}_report.md",
            hypothesis="B improves speed",
            delta=f"B delta {round_idx}",
            strength="fast execution",
            weakness="weaker evidence",
            insight="keep cheap ranker",
            problem="edge-case misses",
            next_move="add evidence filters",
        )
        _write_report(
            reports_root / f"candidate_03_round_{round_idx}_report.md",
            hypothesis="C improves robustness",
            delta=f"C delta {round_idx}",
            strength="best quality",
            weakness="higher complexity",
            insight="add critique loop",
            problem="configuration overhead",
            next_move="ship default templates",
        )

        (reports_root / f"candidate_01_round_{round_idx}_metrics.json").write_text(
            json.dumps({"primary_metric": 0.75 + 0.02 * round_idx, "secondary_metrics": {"latency": 8 + round_idx}}),
            encoding="utf-8",
        )
        (reports_root / f"candidate_02_round_{round_idx}_metrics.json").write_text(
            json.dumps({"primary_metric": 0.70 + 0.02 * round_idx, "secondary_metrics": {"latency": 6 + round_idx}}),
            encoding="utf-8",
        )
        (reports_root / f"candidate_03_round_{round_idx}_metrics.json").write_text(
            json.dumps({"primary_metric": 0.78 + 0.03 * round_idx, "secondary_metrics": {"latency": 9 + round_idx}}),
            encoding="utf-8",
        )

    summary = run_inbox_cycle.run_inbox_cycle(
        run_root=run_root,
        run_id="inbox_run_001",
        problem="Test inbox full cycle",
        candidate_count=3,
        max_rounds=3,
        max_review_cycles=2,
        reports_root=reports_root,
        allow_fallback_rounds=False,
        auto_plan=False,
        candidates_file_input=candidates_file,
        acceptance_file_input=acceptance_file,
        debug_enabled=True,
        debug_console=False,
    )

    run_dir = run_root / "inbox_run_001"
    assert summary["approved"] is True
    assert (run_dir / "deliverables" / "final_conclusion_inbox.json").exists()
    assert (run_dir / "deliverables" / "final_conclusion_inbox.md").exists()
    assert (run_dir / "deliverables" / "pipeline_summary_inbox.json").exists()
    assert (run_dir / "review" / "review_feedback.json").exists()
    assert (run_dir / "runtime" / "inbox" / "implementer.jsonl").exists()
    assert (run_dir / "debug" / "runtime_trace.jsonl").exists()
