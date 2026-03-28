from __future__ import annotations

import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
BLACKBOARD_SCRIPTS = REPO_ROOT / "nanobot/skills/research-blackboard/scripts"
DIGEST_SCRIPTS = REPO_ROOT / "nanobot/skills/research-report-digest/scripts"

for module_dir in (BLACKBOARD_SCRIPTS, DIGEST_SCRIPTS):
    module_str = str(module_dir)
    if module_str not in sys.path:
        sys.path.insert(0, module_str)

from add_peer_feedback import add_peer_feedback
from digest_report import digest_report
from generate_agenda import generate_agenda
from init_research_run import init_research_run
from research_board_lib import extract_candidates, load_json
from synthesize_findings import synthesize_findings
from upsert_worker_entry import upsert_worker_entry
from validate_board import validate_board


@dataclass
class CandidateSpec:
    candidate_id: str
    name: str


def _candidate_id(index: int, candidate: dict[str, Any]) -> str:
    value = candidate.get("candidateId") or candidate.get("candidate_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return f"candidate_{index + 1:02d}"


def _candidate_name(candidate: dict[str, Any], fallback: str) -> str:
    for key in ("name", "title", "planName"):
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _read_candidates(path: Path) -> list[CandidateSpec]:
    raw = load_json(path)
    candidates = extract_candidates(raw)
    output: list[CandidateSpec] = []
    for index, item in enumerate(candidates):
        candidate_id = _candidate_id(index, item)
        output.append(CandidateSpec(candidate_id=candidate_id, name=_candidate_name(item, candidate_id)))
    return output


def _parse_feedback_name(path: Path) -> tuple[str, str]:
    left, marker, right = path.stem.partition("_on_")
    if marker != "_on_" or not left or not right:
        raise ValueError(f"Invalid feedback file name: {path.name}. Expected <from>_on_<to>.json")
    return left, right


def _safe_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _run_paths(run_root: Path, run_id: str) -> tuple[Path, Path, Path]:
    run_dir = run_root / run_id
    board_path = run_dir / "shared" / "worker_board.json"
    agenda_path = run_dir / "shared" / "agenda.json"
    return run_dir, board_path, agenda_path


def _init_session_state() -> None:
    defaults = {
        "run_root": str(REPO_ROOT / ".demo_runs_ui"),
        "run_id": "ui_demo_run_001",
        "problem": "Improve research planning quality",
        "round_index": 1,
        "max_rounds": 3,
        "candidates_file": str(REPO_ROOT / "examples/research-demo/plan/candidates.json"),
        "acceptance_file": str(REPO_ROOT / "examples/research-demo/plan/acceptance_spec.json"),
        "reports_dir": str(REPO_ROOT / "examples/research-demo/reports"),
        "feedback_dir": str(REPO_ROOT / "examples/research-demo/feedback"),
        "review_feedback_file": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _render_paths_overview(run_root: Path, run_id: str) -> tuple[Path, Path, Path]:
    run_dir, board_path, agenda_path = _run_paths(run_root, run_id)
    st.caption("当前运行目录")
    st.code(str(run_dir), language="text")
    col1, col2 = st.columns(2)
    with col1:
        st.write("`worker_board.json`")
        st.code(str(board_path), language="text")
    with col2:
        st.write("`agenda.json`")
        st.code(str(agenda_path), language="text")
    return run_dir, board_path, agenda_path


def _require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")


def _run_full_demo() -> None:
    run_root = Path(st.session_state.run_root)
    run_id = st.session_state.run_id.strip()
    problem = st.session_state.problem.strip()
    candidates_file = Path(st.session_state.candidates_file)
    acceptance_text = st.session_state.acceptance_file.strip()
    acceptance_file = Path(acceptance_text) if acceptance_text else None
    reports_dir = Path(st.session_state.reports_dir)
    feedback_dir = Path(st.session_state.feedback_dir)
    round_index = int(st.session_state.round_index)
    max_rounds = int(st.session_state.max_rounds)

    _require_file(candidates_file, "candidates file")
    if acceptance_file is not None:
        _require_file(acceptance_file, "acceptance file")
    if not reports_dir.exists():
        raise FileNotFoundError(f"reports directory does not exist: {reports_dir}")
    if not feedback_dir.exists():
        raise FileNotFoundError(f"feedback directory does not exist: {feedback_dir}")

    run_dir = init_research_run(
        root=run_root,
        run_id=run_id,
        problem=problem,
        candidates_file=candidates_file,
        acceptance_file=acceptance_file,
        rounds=max_rounds,
    )

    board_path = run_dir / "shared" / "worker_board.json"
    agenda_path = run_dir / "shared" / "agenda.json"

    candidates = _read_candidates(candidates_file)
    for index, candidate in enumerate(candidates, start=1):
        report_path = reports_dir / f"{candidate.candidate_id}_round_{round_index}_report.md"
        metrics_path = reports_dir / f"{candidate.candidate_id}_round_{round_index}_metrics.json"
        _require_file(report_path, f"candidate {index} report")
        _require_file(metrics_path, f"candidate {index} metrics")

        digest_path = run_dir / "shared" / f"{candidate.candidate_id}_digest.json"
        digest_report(
            report_path=report_path,
            metrics_path=metrics_path,
            candidate_id=candidate.candidate_id,
            plan_name=candidate.name,
            round_index=round_index,
            owner=f"worker_{index:02d}",
            output_path=digest_path,
            status="active",
        )
        upsert_worker_entry(board_path, candidate.candidate_id, digest_path)

    for feedback_path in sorted(feedback_dir.glob("*_on_*.json")):
        from_candidate, to_candidate = _parse_feedback_name(feedback_path)
        add_peer_feedback(board_path, from_candidate, to_candidate, feedback_path)

    validate_board(board_path)
    synthesize_findings(board_path)

    review_feedback_text = st.session_state.review_feedback_file.strip()
    review_feedback = Path(review_feedback_text) if review_feedback_text else None
    if review_feedback is not None:
        _require_file(review_feedback, "review feedback file")

    generate_agenda(
        board_path=board_path,
        agenda_path=agenda_path,
        review_feedback_path=review_feedback,
        max_rounds=max_rounds,
    )


def main() -> None:
    st.set_page_config(page_title="Research NanoBot UI", layout="wide")
    st.title("Research NanoBot Local UI")
    st.write(
        "用于本地测试科研多智能体完整流程：初始化 run、生成摘要、写入黑板、融合反馈、生成动态议程。"
    )

    _init_session_state()

    with st.sidebar:
        st.header("运行配置")
        st.text_input("Run Root", key="run_root")
        st.text_input("Run ID", key="run_id")
        st.text_input("Problem", key="problem")
        st.number_input("Round", min_value=1, max_value=10, step=1, key="round_index")
        st.number_input("Max Rounds", min_value=1, max_value=10, step=1, key="max_rounds")
        st.text_input("Candidates File", key="candidates_file")
        st.text_input("Acceptance File (optional)", key="acceptance_file")
        st.text_input("Reports Dir", key="reports_dir")
        st.text_input("Feedback Dir", key="feedback_dir")
        st.text_input("Review Feedback JSON (optional)", key="review_feedback_file")

    run_root = Path(st.session_state.run_root)
    run_id = st.session_state.run_id.strip()
    candidates_file = Path(st.session_state.candidates_file)
    reports_dir = Path(st.session_state.reports_dir)
    feedback_dir = Path(st.session_state.feedback_dir)

    run_dir, board_path, agenda_path = _render_paths_overview(run_root, run_id)

    tabs = st.tabs(["一键全流程", "分步执行", "结果可视化", "帮助"])

    with tabs[0]:
        st.subheader("一键全流程执行")
        st.write("按项目协议顺序执行：初始化 -> digest+upsert -> feedback -> validate -> synthesize -> agenda")
        if st.button("运行完整流程", type="primary"):
            try:
                _run_full_demo()
                st.success("完整流程执行成功。")
            except Exception as exc:  # pragma: no cover
                st.error(str(exc))
                st.code(traceback.format_exc(), language="text")

    with tabs[1]:
        st.subheader("分步执行")

        with st.expander("1) 初始化 run", expanded=True):
            if st.button("初始化", key="btn_init"):
                try:
                    acceptance_text = st.session_state.acceptance_file.strip()
                    acceptance_file = Path(acceptance_text) if acceptance_text else None
                    init_research_run(
                        root=run_root,
                        run_id=run_id,
                        problem=st.session_state.problem.strip(),
                        candidates_file=candidates_file,
                        acceptance_file=acceptance_file,
                        rounds=int(st.session_state.max_rounds),
                    )
                    st.success("初始化完成")
                except Exception as exc:  # pragma: no cover
                    st.error(str(exc))

        with st.expander("2) 生成并写入某个候选方案摘要", expanded=True):
            candidates = []
            if candidates_file.exists():
                try:
                    candidates = _read_candidates(candidates_file)
                except Exception as exc:  # pragma: no cover
                    st.warning(f"读取 candidates 失败: {exc}")

            if not candidates:
                st.info("先确保 Candidates File 可用，再进行摘要提取。")
            else:
                labels = [f"{item.candidate_id} | {item.name}" for item in candidates]
                selected_label = st.selectbox("选择候选方案", labels)
                selected = candidates[labels.index(selected_label)]

                round_index = int(st.session_state.round_index)
                default_report = reports_dir / f"{selected.candidate_id}_round_{round_index}_report.md"
                default_metrics = reports_dir / f"{selected.candidate_id}_round_{round_index}_metrics.json"
                report_path = Path(st.text_input("Report Path", value=str(default_report), key="step_report"))
                metrics_path = Path(st.text_input("Metrics Path", value=str(default_metrics), key="step_metrics"))
                owner = st.text_input("Owner", value="worker_manual", key="step_owner")
                status = st.text_input("Status", value="active", key="step_status")

                if st.button("生成摘要并写入黑板", key="btn_digest_upsert"):
                    try:
                        _require_file(report_path, "report")
                        _require_file(metrics_path, "metrics")
                        _require_file(board_path, "worker board")
                        digest_path = run_dir / "shared" / f"{selected.candidate_id}_digest.json"
                        digest_report(
                            report_path=report_path,
                            metrics_path=metrics_path,
                            candidate_id=selected.candidate_id,
                            plan_name=selected.name,
                            round_index=round_index,
                            owner=owner,
                            output_path=digest_path,
                            status=status,
                        )
                        upsert_worker_entry(board_path, selected.candidate_id, digest_path)
                        st.success(f"{selected.candidate_id} 已写入黑板")
                    except Exception as exc:  # pragma: no cover
                        st.error(str(exc))

        with st.expander("3) 合并 peer feedback", expanded=False):
            files = sorted(feedback_dir.glob("*_on_*.json")) if feedback_dir.exists() else []
            if not files:
                st.info("反馈目录下未发现 *_on_*.json 文件")
            selected = st.multiselect(
                "选择要合并的反馈文件",
                options=[str(path) for path in files],
                default=[str(path) for path in files],
            )
            if st.button("合并所选反馈", key="btn_feedback"):
                try:
                    _require_file(board_path, "worker board")
                    for item in selected:
                        feedback_path = Path(item)
                        from_candidate, to_candidate = _parse_feedback_name(feedback_path)
                        add_peer_feedback(board_path, from_candidate, to_candidate, feedback_path)
                    st.success(f"已合并 {len(selected)} 条反馈")
                except Exception as exc:  # pragma: no cover
                    st.error(str(exc))

        with st.expander("4) 校验、聚合、生成议程", expanded=False):
            if st.button("校验黑板", key="btn_validate"):
                try:
                    validate_board(board_path)
                    st.success("黑板结构合法")
                except Exception as exc:  # pragma: no cover
                    st.error(str(exc))

            if st.button("聚合全局发现", key="btn_synthesize"):
                try:
                    findings = synthesize_findings(board_path)
                    st.success("全局发现已更新")
                    st.json(findings)
                except Exception as exc:  # pragma: no cover
                    st.error(str(exc))

            if st.button("生成下一轮议程", key="btn_agenda"):
                try:
                    review_feedback_text = st.session_state.review_feedback_file.strip()
                    review_feedback = Path(review_feedback_text) if review_feedback_text else None
                    if review_feedback is not None:
                        _require_file(review_feedback, "review feedback file")
                    agenda = generate_agenda(
                        board_path=board_path,
                        agenda_path=agenda_path,
                        review_feedback_path=review_feedback,
                        max_rounds=int(st.session_state.max_rounds),
                    )
                    st.success("agenda 已生成")
                    st.json(agenda)
                except Exception as exc:  # pragma: no cover
                    st.error(str(exc))

    with tabs[2]:
        st.subheader("结果可视化")
        board_data = _safe_json(board_path)
        agenda_data = _safe_json(agenda_path)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("`worker_board.json`")
            if board_data is None:
                st.info("暂未找到 worker_board.json")
            else:
                st.json(board_data)

        with col2:
            st.markdown("`agenda.json`")
            if agenda_data is None:
                st.info("暂未找到 agenda.json")
            else:
                st.json(agenda_data)

        if isinstance(agenda_data, dict):
            st.markdown("### 当前轮次摘要")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Round Index", agenda_data.get("round_index", "-"))
            with col_b:
                st.metric("Active Candidates", len(agenda_data.get("active_candidates", [])))
            with col_c:
                st.metric("Priority Questions", len(agenda_data.get("priority_questions", [])))

    with tabs[3]:
        st.subheader("使用建议")
        st.write("1. 先在 '一键全流程' 跑通，再用 '分步执行' 做定向调试。")
        st.write("2. 当前流程对共享黑板是顺序写入，避免并发写同一个 board 文件。")
        st.write("3. 如果你要接入真实 Worker 输出，保持 digest JSON 字段结构不变。")
        st.code(
            "streamlit run apps/research_flow_ui.py",
            language="bash",
        )


if __name__ == "__main__":
    main()
