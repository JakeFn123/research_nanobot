from __future__ import annotations

import json
import re
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
BLACKBOARD_SCRIPTS = REPO_ROOT / "nanobot/skills/research-blackboard/scripts"
DIGEST_SCRIPTS = REPO_ROOT / "nanobot/skills/research-report-digest/scripts"
IMPLEMENTER_SCRIPTS = REPO_ROOT / "nanobot/skills/research-implementer/scripts"

for module_dir in (BLACKBOARD_SCRIPTS, DIGEST_SCRIPTS, IMPLEMENTER_SCRIPTS):
    module_str = str(module_dir)
    if module_str not in sys.path:
        sys.path.insert(0, module_str)

from add_peer_feedback import add_peer_feedback
from digest_report import digest_report
from finalize_conclusion import finalize_conclusion
from generate_agenda import generate_agenda
from init_research_run import init_research_run
from inbox_lib import list_inbox_messages
from run_full_cycle import run_full_cycle
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


def _safe_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
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


def _path_from_input(value: str) -> Path:
    """Normalize pasted paths by trimming accidental whitespace around each segment."""
    compact = value.replace("\r", "").replace("\n", "").replace("\t", "")
    normalized = "/".join(segment.strip() for segment in compact.split("/"))
    return Path(normalized.strip())


def _resolve_candidate_artifacts(
    reports_dir: Path,
    candidate_id: str,
    round_index: int,
) -> tuple[Path, Path, int, bool]:
    requested_report = reports_dir / f"{candidate_id}_round_{round_index}_report.md"
    requested_metrics = reports_dir / f"{candidate_id}_round_{round_index}_metrics.json"
    if requested_report.exists() and requested_metrics.exists():
        return requested_report, requested_metrics, round_index, False

    pattern = re.compile(rf"^{re.escape(candidate_id)}_round_(\d+)_report\.md$")
    available_rounds: list[int] = []
    for report in reports_dir.glob(f"{candidate_id}_round_*_report.md"):
        match = pattern.match(report.name)
        if not match:
            continue
        candidate_round = int(match.group(1))
        metrics = reports_dir / f"{candidate_id}_round_{candidate_round}_metrics.json"
        if metrics.exists():
            available_rounds.append(candidate_round)

    if not available_rounds:
        raise FileNotFoundError(
            f"No paired report/metrics found for {candidate_id} in {reports_dir}. "
            "Expected files like <candidate_id>_round_<n>_report.md and metrics.json."
        )

    fallback_round = max(available_rounds)
    fallback_report = reports_dir / f"{candidate_id}_round_{fallback_round}_report.md"
    fallback_metrics = reports_dir / f"{candidate_id}_round_{fallback_round}_metrics.json"
    return fallback_report, fallback_metrics, fallback_round, True


def _run_paths(run_root: Path, run_id: str) -> tuple[Path, Path, Path, Path, Path, Path, Path, Path]:
    run_dir = run_root / run_id
    board_path = run_dir / "shared" / "worker_board.json"
    agenda_path = run_dir / "shared" / "agenda.json"
    conclusion_json = run_dir / "deliverables" / "final_conclusion.json"
    conclusion_md = run_dir / "deliverables" / "final_conclusion.md"
    debug_jsonl = run_dir / "debug" / "runtime_trace.jsonl"
    debug_md = run_dir / "debug" / "runtime_trace.md"
    inbox_dir = run_dir / "runtime" / "inbox"
    return run_dir, board_path, agenda_path, conclusion_json, conclusion_md, debug_jsonl, debug_md, inbox_dir


def _init_session_state() -> None:
    defaults = {
        "run_root": str(REPO_ROOT / ".demo_runs_ui"),
        "run_id": "ui_demo_run_001",
        "problem": "Improve research planning quality",
        "round_index": 1,
        "max_rounds": 3,
        "max_review_cycles": 2,
        "candidates_file": str(REPO_ROOT / "examples/research-demo/plan/candidates.json"),
        "acceptance_file": str(REPO_ROOT / "examples/research-demo/plan/acceptance_spec.json"),
        "reports_dir": str(REPO_ROOT / "examples/research-demo/reports"),
        "feedback_dir": str(REPO_ROOT / "examples/research-demo/feedback"),
        "review_feedback_file": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _render_paths_overview(run_root: Path, run_id: str) -> tuple[Path, Path, Path, Path, Path, Path, Path, Path]:
    run_dir, board_path, agenda_path, conclusion_json, conclusion_md, debug_jsonl, debug_md, inbox_dir = _run_paths(
        run_root, run_id
    )
    st.caption("当前运行目录")
    st.code(str(run_dir), language="text")
    col1, col2 = st.columns(2)
    with col1:
        st.write("`worker_board.json`")
        st.code(str(board_path), language="text")
    with col2:
        st.write("`agenda.json`")
        st.code(str(agenda_path), language="text")
    st.write("`deliverables/final_conclusion.json`")
    st.code(str(conclusion_json), language="text")
    st.write("`deliverables/final_conclusion.md`")
    st.code(str(conclusion_md), language="text")
    st.write("`debug/runtime_trace.jsonl`")
    st.code(str(debug_jsonl), language="text")
    st.write("`debug/runtime_trace.md`")
    st.code(str(debug_md), language="text")
    st.write("`runtime/inbox/`")
    st.code(str(inbox_dir), language="text")
    return run_dir, board_path, agenda_path, conclusion_json, conclusion_md, debug_jsonl, debug_md, inbox_dir


def _require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")


def _run_full_demo() -> None:
    run_root = _path_from_input(st.session_state.run_root)
    run_id = st.session_state.run_id.strip()
    problem = st.session_state.problem.strip()
    candidates_file = _path_from_input(st.session_state.candidates_file)
    acceptance_text = st.session_state.acceptance_file.strip()
    acceptance_file = _path_from_input(acceptance_text) if acceptance_text else None
    reports_dir = _path_from_input(st.session_state.reports_dir)
    feedback_dir = _path_from_input(st.session_state.feedback_dir)
    round_index = int(st.session_state.round_index)
    max_rounds = int(st.session_state.max_rounds)

    _require_file(candidates_file, "candidates file")
    if acceptance_file is not None:
        _require_file(acceptance_file, "acceptance file")
    if not reports_dir.exists():
        raise FileNotFoundError(f"reports directory does not exist: {reports_dir}")

    candidate_count = len(_read_candidates(candidates_file))
    candidate_count = max(3, min(5, candidate_count))

    summary = run_full_cycle(
        run_root=run_root,
        run_id=run_id,
        problem=problem,
        candidate_count=candidate_count,
        max_rounds=max_rounds,
        max_review_cycles=int(st.session_state.max_review_cycles),
        reports_root=reports_dir,
        allow_fallback_rounds=True,
        auto_plan=False,
        candidates_file_input=candidates_file,
        acceptance_file_input=acceptance_file,
    )
    st.info(
        "full cycle done, "
        f"approved={summary.get('approved')}, "
        f"winner={summary.get('winner_candidate')}, "
        f"trace={summary.get('debug_trace_jsonl')}"
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
        st.number_input("Max Review Cycles", min_value=1, max_value=10, step=1, key="max_review_cycles")
        st.text_input("Candidates File", key="candidates_file")
        st.text_input("Acceptance File (optional)", key="acceptance_file")
        st.text_input("Reports Dir", key="reports_dir")
        st.text_input("Feedback Dir", key="feedback_dir")
        st.text_input("Review Feedback JSON (optional)", key="review_feedback_file")

    run_root = _path_from_input(st.session_state.run_root)
    run_id = st.session_state.run_id.strip()
    candidates_file = _path_from_input(st.session_state.candidates_file)
    reports_dir = _path_from_input(st.session_state.reports_dir)
    feedback_dir = _path_from_input(st.session_state.feedback_dir)

    (
        run_dir,
        board_path,
        agenda_path,
        conclusion_json_path,
        conclusion_md_path,
        debug_jsonl_path,
        debug_md_path,
        inbox_dir_path,
    ) = _render_paths_overview(run_root, run_id)

    tabs = st.tabs(["一键全流程", "分步执行", "结果可视化", "结论", "调试日志", "Inbox通信", "帮助"])

    with tabs[0]:
        st.subheader("一键全流程执行")
        st.write(
            "按项目协议顺序执行：初始化 -> digest+upsert -> feedback -> validate -> synthesize -> agenda -> conclusion"
        )
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
                    acceptance_file = _path_from_input(acceptance_text) if acceptance_text else None
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
                report_path = _path_from_input(
                    st.text_input("Report Path", value=str(default_report), key="step_report")
                )
                metrics_path = _path_from_input(
                    st.text_input("Metrics Path", value=str(default_metrics), key="step_metrics")
                )
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
                    review_feedback = _path_from_input(review_feedback_text) if review_feedback_text else None
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

        with st.expander("5) 生成最终结论", expanded=False):
            if st.button("生成结论文件", key="btn_finalize"):
                try:
                    _require_file(board_path, "worker board")
                    _require_file(agenda_path, "agenda")
                    review_feedback_text = st.session_state.review_feedback_file.strip()
                    review_feedback = _path_from_input(review_feedback_text) if review_feedback_text else None
                    if review_feedback is not None:
                        _require_file(review_feedback, "review feedback file")
                    conclusion = finalize_conclusion(
                        board_path=board_path,
                        agenda_path=agenda_path,
                        output_json=conclusion_json_path,
                        output_md=conclusion_md_path,
                        review_feedback_path=review_feedback,
                    )
                    st.success("final_conclusion 已生成")
                    st.json(conclusion)
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
        st.subheader("结论输出")
        conclusion_json = _safe_json(conclusion_json_path)
        if conclusion_json is None:
            st.info("暂未找到 final_conclusion.json，请先在“分步执行”或“一键全流程”生成。")
        else:
            st.markdown("`final_conclusion.json`")
            st.json(conclusion_json)

        st.markdown("`final_conclusion.md`")
        if conclusion_md_path.exists():
            st.code(conclusion_md_path.read_text(encoding="utf-8"), language="markdown")
        else:
            st.info("暂未找到 final_conclusion.md")

    with tabs[4]:
        st.subheader("调试日志")
        rows = _safe_jsonl(debug_jsonl_path)
        if not rows:
            st.info("暂未找到 runtime trace，请先运行一键全流程。")
        else:
            st.metric("Trace Events", len(rows))
            st.dataframe(rows, use_container_width=True, hide_index=True)

        st.markdown("`runtime_trace.md`")
        if debug_md_path.exists():
            st.code(debug_md_path.read_text(encoding="utf-8"), language="markdown")
        else:
            st.info("暂未找到 runtime_trace.md")

    with tabs[5]:
        st.subheader("Inbox 通信")
        if not inbox_dir_path.exists():
            st.info("暂未找到 runtime/inbox 目录。可运行 inbox 模式后查看。")
        else:
            rows = list_inbox_messages(run_dir)
            if not rows:
                st.info("inbox 目录存在，但暂未发现消息。")
            else:
                roles = sorted({str(item.get("_inbox_role", "")).strip() for item in rows if str(item.get("_inbox_role", "")).strip()})
                role_pick = st.selectbox("按角色过滤", ["(all)"] + roles, index=0)
                type_values = sorted({str(item.get("type", "")).strip() for item in rows if str(item.get("type", "")).strip()})
                type_pick = st.selectbox("按消息类型过滤", ["(all)"] + type_values, index=0)
                round_values = sorted({int(item.get("round", 0) or 0) for item in rows if isinstance(item.get("round", 0), int)})
                round_pick = st.selectbox("按轮次过滤", ["(all)"] + [str(v) for v in round_values], index=0)

                filtered: list[dict[str, Any]] = []
                for row in rows:
                    if role_pick != "(all)" and str(row.get("_inbox_role", "")) != role_pick:
                        continue
                    if type_pick != "(all)" and str(row.get("type", "")) != type_pick:
                        continue
                    if round_pick != "(all)" and int(row.get("round", -1) or -1) != int(round_pick):
                        continue
                    filtered.append(row)

                st.metric("Inbox Messages", len(filtered))
                st.dataframe(filtered, use_container_width=True, hide_index=True)

    with tabs[6]:
        st.subheader("使用建议")
        st.write("1. 先在 '一键全流程' 跑通，再用 '分步执行' 做定向调试。")
        st.write("2. 当前流程对共享黑板是顺序写入，避免并发写同一个 board 文件。")
        st.write("3. 评审通过后再生成结论文件，可直接作为阶段性交付结果。")
        st.write("4. 调试页签会展示每一步运行日志，便于定位失败步骤。")
        st.write("5. 如果你要接入真实 Worker 输出，保持 digest JSON 字段结构不变。")
        st.code(
            "streamlit run apps/research_flow_ui.py",
            language="bash",
        )


if __name__ == "__main__":
    main()
