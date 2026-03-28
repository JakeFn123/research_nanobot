import importlib
import sys
from pathlib import Path


BLACKBOARD_SCRIPT_DIR = Path("nanobot/skills/research-blackboard/scripts").resolve()
if str(BLACKBOARD_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(BLACKBOARD_SCRIPT_DIR))

REPORT_DIGEST_SCRIPT_DIR = Path("nanobot/skills/research-report-digest/scripts").resolve()
if str(REPORT_DIGEST_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(REPORT_DIGEST_SCRIPT_DIR))

PLANNER_SCRIPT_DIR = Path("nanobot/skills/research-planner/scripts").resolve()
if str(PLANNER_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(PLANNER_SCRIPT_DIR))

IMPLEMENTER_SCRIPT_DIR = Path("nanobot/skills/research-implementer/scripts").resolve()
if str(IMPLEMENTER_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(IMPLEMENTER_SCRIPT_DIR))

REVIEWER_SCRIPT_DIR = Path("nanobot/skills/research-reviewer/scripts").resolve()
if str(REVIEWER_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(REVIEWER_SCRIPT_DIR))

init_research_run = importlib.import_module("init_research_run")
validate_board = importlib.import_module("validate_board")
upsert_worker_entry = importlib.import_module("upsert_worker_entry")
add_peer_feedback = importlib.import_module("add_peer_feedback")
synthesize_findings = importlib.import_module("synthesize_findings")
generate_agenda = importlib.import_module("generate_agenda")
finalize_conclusion = importlib.import_module("finalize_conclusion")
digest_report = importlib.import_module("digest_report")
generate_plan_bundle = importlib.import_module("generate_plan_bundle")
run_full_cycle = importlib.import_module("run_full_cycle")
review_run = importlib.import_module("review_run")
research_board_lib = importlib.import_module("research_board_lib")


def test_init_research_run_creates_expected_structure(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(
        (
            '[{"candidateId":"candidate_01","name":"Plan A","hypothesis":"A works","implementationSpec":"Build A"},'
            '{"candidateId":"candidate_02","name":"Plan B","hypothesis":"B works","implementationSpec":"Build B"}]\n'
        ),
        encoding="utf-8",
    )
    acceptance_path = tmp_path / "acceptance_spec.json"
    acceptance_path.write_text('{"hard_requirements":["must run"]}\n', encoding="utf-8")

    run_dir = init_research_run.init_research_run(
        root=tmp_path / "research_runs",
        run_id="run_001",
        problem="Test dynamic collaboration",
        candidates_file=candidates_path,
        acceptance_file=acceptance_path,
        rounds=3,
    )

    assert run_dir == tmp_path / "research_runs" / "run_001"
    assert (run_dir / "shared" / "worker_board.json").exists()
    assert (run_dir / "shared" / "agenda.json").exists()
    assert (run_dir / "implementation" / "candidate_01" / "round_3").exists()
    assert (run_dir / "implementation" / "candidate_02" / "round_2").exists()

    board = research_board_lib.load_json(run_dir / "shared" / "worker_board.json")
    assert board["workers"]["candidate_01"]["plan_name"] == "Plan A"
    assert board["workers"]["candidate_02"]["key_hypothesis"] == "B works"


def test_digest_report_and_upsert_worker_entry_roundtrip(tmp_path: Path) -> None:
    report_path = tmp_path / "report.md"
    report_path.write_text(
        (
            "## Key Hypothesis\n"
            "Use retrieval before decomposition.\n\n"
            "## Implementation Delta\n"
            "- added retrieval stage\n"
            "- added scoring stage\n\n"
            "## Strengths\n"
            "- stable planning\n\n"
            "## Weaknesses\n"
            "- slower latency\n\n"
            "## Transferable Insights\n"
            "- early retrieval filters weak paths\n\n"
            "## Open Problems\n"
            "- diversity still limited\n\n"
            "## Proposed Next Move\n"
            "- add diversity constraint\n"
        ),
        encoding="utf-8",
    )
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        '{"primary_metric":0.73,"secondary_metrics":{"latency_ms":910,"cost_usd":0.44}}\n',
        encoding="utf-8",
    )
    digest_path = tmp_path / "digest.json"

    digest_report.digest_report(
        report_path=report_path,
        metrics_path=metrics_path,
        candidate_id="candidate_01",
        plan_name="Plan A",
        round_index=1,
        owner="worker_01",
        output_path=digest_path,
    )

    board_path = tmp_path / "worker_board.json"
    research_board_lib.save_json(
        board_path,
        {
            "run_id": "run_001",
            "problem": "demo",
            "acceptance_spec_path": "plan/acceptance_spec.json",
            "round_index": 0,
            "workers": {},
            "peer_feedback": {},
            "global_findings": {},
        },
    )
    upsert_worker_entry.upsert_worker_entry(board_path, "candidate_01", digest_path)
    validate_board.validate_board(board_path)

    board = research_board_lib.load_json(board_path)
    assert board["round_index"] == 1
    assert board["workers"]["candidate_01"]["strengths"] == ["stable planning"]
    assert board["workers"]["candidate_01"]["core_metrics"]["primary_metric"] == 0.73


def test_feedback_findings_and_agenda_generation(tmp_path: Path) -> None:
    board_path = tmp_path / "worker_board.json"
    research_board_lib.save_json(
        board_path,
        {
            "run_id": "run_001",
            "problem": "demo",
            "acceptance_spec_path": "plan/acceptance_spec.json",
            "round_index": 1,
            "workers": {
                "candidate_01": {
                    "owner": "worker_01",
                    "plan_name": "Plan A",
                    "round": 1,
                    "status": "active",
                    "key_hypothesis": "A",
                    "implementation_delta": ["added retrieval"],
                    "core_metrics": {"primary_metric": 0.72, "secondary_metrics": {"latency_ms": 900}},
                    "strengths": ["strong filtering"],
                    "weaknesses": ["high latency"],
                    "transferable_insights": ["retrieval-first rejects weak ideas"],
                    "open_problems": ["not diverse enough"],
                    "proposed_next_move": ["reduce retrieval cost"],
                    "private_report_path": "implementation/candidate_01/round_1/report.md",
                },
                "candidate_02": {
                    "owner": "worker_02",
                    "plan_name": "Plan B",
                    "round": 1,
                    "status": "active",
                    "key_hypothesis": "B",
                    "implementation_delta": ["added ranking"],
                    "core_metrics": {"primary_metric": 0.68, "secondary_metrics": {"latency_ms": 500}},
                    "strengths": ["cheap execution"],
                    "weaknesses": ["weak rejection"],
                    "transferable_insights": ["ranking heuristic is cheap"],
                    "open_problems": ["misses hard negatives"],
                    "proposed_next_move": ["borrow strong filter from Plan A"],
                    "private_report_path": "implementation/candidate_02/round_1/report.md",
                },
            },
            "peer_feedback": {},
            "global_findings": {},
        },
    )

    feedback_path = tmp_path / "feedback.json"
    research_board_lib.save_json(
        feedback_path,
        {
            "observed_strengths": ["strong filtering"],
            "observed_weaknesses": ["high latency"],
            "borrowable_ideas": ["split broad retrieval from deep retrieval"],
            "suggested_improvement": ["keep filtering but lower retrieval cost"],
        },
    )
    add_peer_feedback.add_peer_feedback(
        board_path=board_path,
        from_candidate="candidate_02",
        to_candidate="candidate_01",
        feedback_path=feedback_path,
    )

    findings = synthesize_findings.synthesize_findings(board_path)
    assert "strong filtering" in findings["dominant_strengths"]
    assert findings["candidate_rank_hint"][0]["candidate_id"] == "candidate_01"

    agenda_path = tmp_path / "agenda.json"
    agenda = generate_agenda.generate_agenda(board_path, agenda_path, max_rounds=3)
    assert agenda["round_index"] == 2
    assert "candidate_01" in agenda["worker_actions"]
    assert any("retrieval" in item.lower() for item in agenda["worker_actions"]["candidate_01"])


def test_generate_agenda_uses_review_feedback_after_review(tmp_path: Path) -> None:
    board_path = tmp_path / "worker_board.json"
    research_board_lib.save_json(
        board_path,
        {
            "run_id": "run_001",
            "problem": "demo",
            "acceptance_spec_path": "plan/acceptance_spec.json",
            "round_index": 3,
            "workers": {
                "candidate_01": {
                    "owner": "worker_01",
                    "plan_name": "Plan A",
                    "round": 3,
                    "status": "active",
                    "key_hypothesis": "A",
                    "implementation_delta": [],
                    "core_metrics": {"primary_metric": 0.75, "secondary_metrics": {}},
                    "strengths": [],
                    "weaknesses": [],
                    "transferable_insights": [],
                    "open_problems": [],
                    "proposed_next_move": [],
                    "private_report_path": "implementation/candidate_01/round_3/report.md",
                }
            },
            "peer_feedback": {},
            "global_findings": {},
        },
    )
    review_feedback_path = tmp_path / "review_feedback.json"
    research_board_lib.save_json(
        review_feedback_path,
        {
            "approved": False,
            "must_fix": ["add a baseline comparison"],
            "optional_improvements": [],
            "evidence": ["baseline missing"],
        },
    )

    agenda = generate_agenda.generate_agenda(
        board_path=board_path,
        agenda_path=tmp_path / "agenda.json",
        review_feedback_path=review_feedback_path,
        max_rounds=3,
    )

    assert agenda["ready_for_review"] is False
    assert agenda["round_index"] == 4
    assert "add a baseline comparison" in agenda["worker_actions"]["candidate_01"]


def test_finalize_conclusion_generates_delivery_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_001"
    board_path = run_dir / "shared" / "worker_board.json"
    agenda_path = run_dir / "shared" / "agenda.json"
    review_feedback_path = run_dir / "review" / "review_feedback.json"
    acceptance_path = run_dir / "plan" / "acceptance_spec.json"

    research_board_lib.save_json(
        board_path,
        {
            "run_id": "run_001",
            "problem": "demo",
            "acceptance_spec_path": "plan/acceptance_spec.json",
            "round_index": 3,
            "workers": {
                "candidate_01": {
                    "owner": "worker_01",
                    "plan_name": "Plan A",
                    "round": 3,
                    "status": "active",
                    "key_hypothesis": "A",
                    "implementation_delta": [],
                    "core_metrics": {"primary_metric": 0.81, "secondary_metrics": {}},
                    "strengths": ["good stability"],
                    "weaknesses": ["high cost"],
                    "transferable_insights": [],
                    "open_problems": [],
                    "proposed_next_move": ["add one final regression check"],
                    "private_report_path": "implementation/candidate_01/round_3/report.md",
                }
            },
            "peer_feedback": {},
            "global_findings": {
                "dominant_strengths": ["good stability"],
                "dominant_failures": ["high cost"],
                "candidate_rank_hint": [
                    {
                        "candidate_id": "candidate_01",
                        "primary_metric": 0.81,
                        "praise_score": 2,
                        "concern_score": 1,
                    }
                ],
                "fusion_opportunities": [],
                "improvement_targets": ["optimize cost without harming stability"],
            },
        },
    )
    research_board_lib.save_json(
        agenda_path,
        {
            "round_index": 3,
            "ready_for_review": True,
            "active_candidates": ["candidate_01"],
            "priority_questions": [],
            "worker_actions": {"candidate_01": ["optimize cost"]},
        },
    )
    research_board_lib.save_json(
        review_feedback_path,
        {
            "approved": True,
            "must_fix": [],
            "optional_improvements": ["add one ablation table"],
            "evidence": ["all hard checks passed"],
        },
    )
    research_board_lib.save_json(
        acceptance_path,
        {
            "hard_requirements": ["all hard checks passed"],
            "soft_requirements": ["cost should be optimized"],
            "review_checks": [{"name": "validate_board_shape", "required": True}],
        },
    )

    conclusion = finalize_conclusion.finalize_conclusion(
        board_path=board_path,
        agenda_path=agenda_path,
        output_json=run_dir / "deliverables" / "final_conclusion.json",
        output_md=run_dir / "deliverables" / "final_conclusion.md",
        review_feedback_path=review_feedback_path,
    )

    assert conclusion["readiness"]["review_status"] == "approved"
    assert conclusion["readiness"]["ready_for_delivery"] is True
    assert conclusion["selected_solution"]["winner_candidate_id"] == "candidate_01"
    assert (run_dir / "deliverables" / "final_conclusion.json").exists()
    assert (run_dir / "deliverables" / "final_conclusion.md").exists()


def test_finalize_conclusion_blocks_delivery_on_rejected_review(tmp_path: Path) -> None:
    board_path = tmp_path / "worker_board.json"
    agenda_path = tmp_path / "agenda.json"
    review_feedback_path = tmp_path / "review_feedback.json"

    research_board_lib.save_json(
        board_path,
        {
            "run_id": "run_002",
            "problem": "demo",
            "acceptance_spec_path": "",
            "round_index": 2,
            "workers": {
                "candidate_01": {
                    "owner": "worker_01",
                    "plan_name": "Plan A",
                    "round": 2,
                    "status": "active",
                    "key_hypothesis": "A",
                    "implementation_delta": [],
                    "core_metrics": {"primary_metric": 0.70, "secondary_metrics": {}},
                    "strengths": ["stable"],
                    "weaknesses": ["no baseline"],
                    "transferable_insights": [],
                    "open_problems": [],
                    "proposed_next_move": [],
                    "private_report_path": "implementation/candidate_01/round_2/report.md",
                }
            },
            "peer_feedback": {},
            "global_findings": {
                "dominant_strengths": ["stable"],
                "dominant_failures": ["no baseline"],
                "candidate_rank_hint": [],
                "fusion_opportunities": [],
                "improvement_targets": ["add baseline comparison"],
            },
        },
    )
    research_board_lib.save_json(
        agenda_path,
        {
            "round_index": 3,
            "ready_for_review": False,
            "active_candidates": ["candidate_01"],
            "priority_questions": [],
            "worker_actions": {},
        },
    )
    research_board_lib.save_json(
        review_feedback_path,
        {
            "approved": False,
            "must_fix": ["add baseline comparison"],
            "optional_improvements": [],
            "evidence": ["baseline is missing"],
        },
    )

    conclusion = finalize_conclusion.finalize_conclusion(
        board_path=board_path,
        agenda_path=agenda_path,
        output_json=tmp_path / "final_conclusion.json",
        output_md=tmp_path / "final_conclusion.md",
        review_feedback_path=review_feedback_path,
    )

    assert conclusion["readiness"]["review_status"] == "rejected"
    assert conclusion["readiness"]["ready_for_delivery"] is False
    assert "add baseline comparison" in conclusion["next_actions"]


def test_generate_plan_bundle_writes_required_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_plan"
    summary = generate_plan_bundle.generate_plan_bundle(
        problem="Improve planning quality with low latency",
        output_dir=run_dir,
        candidate_count=3,
        search_results=1,
    )

    assert summary["candidate_count"] == 3
    assert (run_dir / "plan" / "candidates.json").exists()
    assert (run_dir / "plan" / "acceptance_spec.json").exists()
    assert (run_dir / "plan" / "plan_brief.md").exists()


def test_run_full_cycle_end_to_end_with_reviewer_and_conclusion(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    run_id = "full_cycle_001"
    reports_root = tmp_path / "reports"

    candidates_payload = [
        {"candidateId": "candidate_01", "name": "Plan A"},
        {"candidateId": "candidate_02", "name": "Plan B"},
        {"candidateId": "candidate_03", "name": "Plan C"},
    ]
    acceptance_payload = {
        "hard_requirements": [
            "shared board can be initialized",
            "worker digests can be published",
            "peer feedback can be merged",
            "agenda can be generated from board findings",
            "review feedback can be generated with tool evidence",
            "final conclusion artifacts can be generated",
        ],
        "soft_requirements": [],
        "review_checks": [
            {"name": "validate_board_shape", "tool": "exec", "required": True},
            {"name": "generate_next_agenda", "tool": "exec", "required": True},
        ],
    }
    candidates_file = tmp_path / "candidates.json"
    acceptance_file = tmp_path / "acceptance.json"
    research_board_lib.save_json(candidates_file, candidates_payload)
    research_board_lib.save_json(acceptance_file, acceptance_payload)

    for round_index in (1, 2, 3):
        for idx, candidate_id in enumerate(("candidate_01", "candidate_02", "candidate_03"), start=1):
            report = reports_root / f"{candidate_id}_round_{round_index}_report.md"
            metrics = reports_root / f"{candidate_id}_round_{round_index}_metrics.json"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(
                (
                    "## Key Hypothesis\n"
                    f"{candidate_id} hypothesis\n\n"
                    "## Implementation Delta\n"
                    f"- change r{round_index}\n\n"
                    "## Strengths\n"
                    f"- strength {idx}\n\n"
                    "## Weaknesses\n"
                    f"- weakness {idx}\n\n"
                    "## Transferable Insights\n"
                    f"- insight {idx}\n\n"
                    "## Open Problems\n"
                    f"- problem {idx}\n\n"
                    "## Proposed Next Move\n"
                    f"- next move {idx}\n"
                ),
                encoding="utf-8",
            )
            research_board_lib.save_json(
                metrics,
                {
                    "primary_metric": 0.80 - (idx * 0.03) + (round_index * 0.01),
                    "secondary_metrics": {"latency_ms": 800 + idx},
                },
            )

    summary = run_full_cycle.run_full_cycle(
        run_root=run_root,
        run_id=run_id,
        problem="Test full cycle",
        candidate_count=3,
        max_rounds=3,
        max_review_cycles=2,
        reports_root=reports_root,
        allow_fallback_rounds=False,
        auto_plan=False,
        candidates_file_input=candidates_file,
        acceptance_file_input=acceptance_file,
    )

    run_dir = run_root / run_id
    assert summary["approved"] is True
    assert (run_dir / "review" / "review_feedback.json").exists()
    assert (run_dir / "review" / "review_report.md").exists()
    assert (run_dir / "deliverables" / "final_conclusion.json").exists()
    assert (run_dir / "deliverables" / "final_conclusion.md").exists()

    review_feedback = research_board_lib.load_json(run_dir / "review" / "review_feedback.json")
    assert review_feedback["approved"] is True
