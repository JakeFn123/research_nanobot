import importlib
import sys
from pathlib import Path


BLACKBOARD_SCRIPT_DIR = Path("nanobot/skills/research-blackboard/scripts").resolve()
if str(BLACKBOARD_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(BLACKBOARD_SCRIPT_DIR))

REPORT_DIGEST_SCRIPT_DIR = Path("nanobot/skills/research-report-digest/scripts").resolve()
if str(REPORT_DIGEST_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(REPORT_DIGEST_SCRIPT_DIR))

init_research_run = importlib.import_module("init_research_run")
validate_board = importlib.import_module("validate_board")
upsert_worker_entry = importlib.import_module("upsert_worker_entry")
add_peer_feedback = importlib.import_module("add_peer_feedback")
synthesize_findings = importlib.import_module("synthesize_findings")
generate_agenda = importlib.import_module("generate_agenda")
digest_report = importlib.import_module("digest_report")
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
