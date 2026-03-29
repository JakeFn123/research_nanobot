from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTER_SCRIPTS = REPO_ROOT / "nanobot/skills/research-implementer/scripts"
BLACKBOARD_SCRIPTS = REPO_ROOT / "nanobot/skills/research-blackboard/scripts"

for module_dir in (IMPLEMENTER_SCRIPTS, BLACKBOARD_SCRIPTS):
    module_str = str(module_dir)
    if module_str not in sys.path:
        sys.path.insert(0, module_str)

from inbox_lib import list_inbox_messages
from research_board_lib import extract_candidates, load_json
from run_inbox_cycle import run_inbox_cycle


@dataclass
class RunFiles:
    run_dir: Path
    trace_json: Path
    trace_jsonl: Path
    trace_health_json: Path
    trace_md: Path
    message_threads_json: Path
    pipeline_summary: Path
    final_conclusion_json: Path
    final_conclusion_md: Path
    review_feedback: Path
    review_report: Path
    inbox_dir: Path


def _path_from_input(value: str) -> Path:
    compact = value.replace("\r", "").replace("\n", "").replace("\t", "")
    normalized = "/".join(segment.strip() for segment in compact.split("/"))
    return Path(normalized.strip())


def _run_files(run_root: Path, run_id: str) -> RunFiles:
    run_dir = run_root / run_id
    return RunFiles(
        run_dir=run_dir,
        trace_json=run_dir / "debug" / "runtime_trace.json",
        trace_jsonl=run_dir / "debug" / "runtime_trace.jsonl",
        trace_health_json=run_dir / "debug" / "runtime_trace_health.json",
        trace_md=run_dir / "debug" / "runtime_trace.md",
        message_threads_json=run_dir / "debug" / "message_threads.json",
        pipeline_summary=run_dir / "deliverables" / "pipeline_summary_inbox.json",
        final_conclusion_json=run_dir / "deliverables" / "final_conclusion_inbox.json",
        final_conclusion_md=run_dir / "deliverables" / "final_conclusion_inbox.md",
        review_feedback=run_dir / "review" / "review_feedback.json",
        review_report=run_dir / "review" / "review_report.md",
        inbox_dir=run_dir / "runtime" / "inbox",
    )


def _safe_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _load_trace_events(files: RunFiles) -> list[dict[str, Any]]:
    payload = _load_trace_payload(files)
    if isinstance(payload, dict) and isinstance(payload.get("events"), list):
        events: list[dict[str, Any]] = []
        for event in payload["events"]:
            if isinstance(event, dict):
                events.append(event)
        return events
    return _safe_jsonl(files.trace_jsonl)


def _load_trace_payload(files: RunFiles) -> dict[str, Any] | None:
    payload = _safe_json(files.trace_json)
    if isinstance(payload, dict):
        return payload
    return None


def _team_stats(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    role_set: set[str] = set()
    for msg in messages:
        sender = str(msg.get("from", "")).strip()
        receiver = str(msg.get("to", "")).strip()
        if sender:
            role_set.add(sender)
        if receiver:
            role_set.add(receiver)

    stats: list[dict[str, Any]] = []
    for role in sorted(role_set):
        sent = [m for m in messages if str(m.get("from", "")) == role]
        received = [m for m in messages if str(m.get("to", "")) == role]
        last_message = ""
        if received:
            latest = sorted(received, key=lambda m: str(m.get("ts_utc", "")))[-1]
            last_message = f"{latest.get('type', '')} @ {latest.get('round', '-') }"
        stats.append(
            {
                "role": role,
                "sent": len(sent),
                "received": len(received),
                "last_message": last_message,
            }
        )
    return stats


def _edge_rows(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for msg in messages:
        sender = str(msg.get("from", "")).strip()
        receiver = str(msg.get("to", "")).strip()
        if not sender or not receiver:
            continue
        grouped[(sender, receiver)].append(msg)

    rows: list[dict[str, Any]] = []
    for (sender, receiver), rows_msg in sorted(grouped.items()):
        type_counter = Counter(str(m.get("type", "")).strip() for m in rows_msg)
        top_types = [f"{name}:{count}" for name, count in type_counter.most_common(2) if name]
        rows.append(
            {
                "from": sender,
                "to": receiver,
                "count": len(rows_msg),
                "top_types": ", ".join(top_types),
            }
        )
    return rows


def _safe_label(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_") or "role"


def _role_color(role: str) -> str:
    if role == "planner":
        return "#dbeafe"
    if role == "implementer":
        return "#dcfce7"
    if role == "reviewer":
        return "#fee2e2"
    if role.startswith("worker_"):
        return "#fef3c7"
    return "#f3f4f6"


def _build_graphviz(messages: list[dict[str, Any]]) -> str:
    roles = sorted({str(m.get("from", "")).strip() for m in messages} | {str(m.get("to", "")).strip() for m in messages})
    edges = _edge_rows(messages)

    lines = [
        "digraph AgentTeam {",
        "  rankdir=LR;",
        "  splines=true;",
        "  node [shape=box, style=\"rounded,filled\", color=\"#374151\", fontname=\"Helvetica\"];",
        "  edge [color=\"#6b7280\", fontname=\"Helvetica\"];",
    ]

    for role in roles:
        if not role:
            continue
        node_id = _safe_label(role)
        lines.append(f'  {node_id} [label="{role}", fillcolor="{_role_color(role)}"];')

    for row in edges:
        src = _safe_label(row["from"])
        dst = _safe_label(row["to"])
        label = f'{row["count"]} msgs'
        if row["top_types"]:
            label = f'{label}\\n{row["top_types"]}'
        lines.append(f'  {src} -> {dst} [label="{label}"];')

    lines.append("}")
    return "\n".join(lines)


def _candidate_count(candidates_file: Path) -> int:
    payload = load_json(candidates_file)
    rows = extract_candidates(payload)
    size = len(rows)
    if size < 3:
        return 3
    if size > 5:
        return 5
    return size


def _render_event_detail(events: list[dict[str, Any]], trace_payload: dict[str, Any] | None) -> None:
    st.subheader("Pipeline Step Debug I/O")
    if not events:
        st.info("未找到调试事件。请先运行一次 Team+Inbox 全流程。")
        return

    lane_names = sorted({str(event.get("lane_id", "")).strip() for event in events if str(event.get("lane_id", "")).strip()})
    event_types = sorted({str(event.get("event_type", "")).strip() for event in events if str(event.get("event_type", "")).strip()})
    phase_names = sorted({str(event.get("phase", "")).strip() for event in events if str(event.get("phase", "")).strip()})
    step_names = [str(event.get("step", "")) for event in events]

    if isinstance(trace_payload, dict):
        summary = trace_payload.get("summary", {})
        if isinstance(summary, dict):
            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                st.metric("事件总数", int(summary.get("event_count", len(events)) or len(events)))
            with col_b:
                st.metric("Lane 数", int(trace_payload.get("lane_count", len(lane_names)) or len(lane_names)))
            with col_c:
                st.metric("开放调用数", int(summary.get("open_call_count", 0) or 0))
            with col_d:
                st.metric("异常 phase 数", int(summary.get("invalid_phase_events", 0) or 0))

    idx = st.slider("按事件索引回放", min_value=1, max_value=len(events), value=len(events), step=1)
    current = events[idx - 1]

    selected_lane = st.selectbox("按 lane 过滤", options=["(all)"] + lane_names, index=0)
    selected_event_type = st.selectbox("按 event_type 过滤", options=["(all)"] + event_types, index=0)
    selected_phase = st.selectbox("按 phase 过滤", options=["(all)"] + phase_names, index=0)
    selected_step = st.selectbox("按步骤过滤", options=["(all)"] + sorted(set(step_names)), index=0)
    call_id_pick = st.text_input("按 call_id 过滤（可选）").strip()
    message_id_pick = st.text_input("按 message_id 过滤（可选）").strip()

    filtered = events
    if selected_lane != "(all)":
        filtered = [event for event in filtered if str(event.get("lane_id", "")) == selected_lane]
    if selected_event_type != "(all)":
        filtered = [event for event in filtered if str(event.get("event_type", "")) == selected_event_type]
    if selected_phase != "(all)":
        filtered = [event for event in filtered if str(event.get("phase", "")) == selected_phase]
    if selected_step != "(all)":
        filtered = [event for event in filtered if str(event.get("step", "")) == selected_step]
    if call_id_pick:
        filtered = [event for event in filtered if str(event.get("call_id", "")).strip() == call_id_pick]
    if message_id_pick:
        filtered = [event for event in filtered if str(event.get("message_id", "")).strip() == message_id_pick]

    st.metric("过滤后步骤数", len(filtered))
    st.markdown("**当前事件详情**")
    st.json(current)

    preview_rows: list[dict[str, Any]] = []
    for event in filtered:
        details = event.get("details", {}) if isinstance(event.get("details"), dict) else {}
        preview_rows.append(
            {
                "index": event.get("index", ""),
                "time_utc": event.get("time_utc", ""),
                "status": event.get("status", ""),
                "lane_id": event.get("lane_id", ""),
                "event_type": event.get("event_type", ""),
                "phase": event.get("phase", ""),
                "step": event.get("step", ""),
                "call_id": event.get("call_id", ""),
                "message_id": event.get("message_id", ""),
                "duration_ms": event.get("duration_ms", ""),
                "message": event.get("message", ""),
                "input_keys": ",".join(sorted((details.get("inputs", {}) or {}).keys())) if isinstance(details, dict) else "",
                "output_keys": ",".join(sorted((details.get("outputs", {}) or {}).keys())) if isinstance(details, dict) else "",
            }
        )

    st.dataframe(preview_rows, use_container_width=True, hide_index=True)


def _render_thread_diagnostics(files: RunFiles, messages: list[dict[str, Any]]) -> None:
    st.subheader("通信线程与回包健康度")
    payload = _safe_json(files.message_threads_json)
    if not isinstance(payload, dict):
        st.info("未找到 message_threads.json，显示在线计算的基础统计。")
        if not messages:
            return
        grouped: dict[str, int] = defaultdict(int)
        for msg in messages:
            key = str(msg.get("thread_id", "")).strip() or str(msg.get("correlation_id", "")).strip() or "unthreaded"
            grouped[key] += 1
        rows = [{"thread_id": key, "message_count": count} for key, count in sorted(grouped.items(), key=lambda item: (-item[1], item[0]))]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("消息总数", int(payload.get("message_count", 0) or 0))
    with col2:
        st.metric("线程数", int(payload.get("thread_count", 0) or 0))
    with col3:
        st.metric("reply 边数", int(payload.get("reply_edge_count", 0) or 0))
    with col4:
        st.metric("孤儿 reply", int(payload.get("orphan_reply_count", 0) or 0))

    threads = payload.get("threads", [])
    if isinstance(threads, list) and threads:
        st.markdown("**线程统计（Top）**")
        st.dataframe(threads[:30], use_container_width=True, hide_index=True)

    orphans = payload.get("orphan_replies", [])
    if isinstance(orphans, list) and orphans:
        st.markdown("**孤儿 reply（需排查）**")
        st.dataframe(orphans, use_container_width=True, hide_index=True)


def _round_progress(run_dir: Path) -> list[dict[str, Any]]:
    summary_dir = run_dir / "runtime" / "round_summaries"
    if not summary_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for file_path in sorted(summary_dir.glob("round_*.json")):
        payload = _safe_json(file_path)
        if not isinstance(payload, dict):
            continue
        round_idx = int(payload.get("round", 0) or 0)
        for rank in payload.get("candidate_rank_hint", []):
            if not isinstance(rank, dict):
                continue
            rows.append(
                {
                    "round": round_idx,
                    "candidate_id": str(rank.get("candidate_id", "")),
                    "primary_metric": float(rank.get("primary_metric", 0.0) or 0.0),
                }
            )
    return rows


def _init_state() -> None:
    defaults = {
        "run_root": str(REPO_ROOT / ".demo_runs_backend"),
        "run_id": "interactive_demo_001",
        "problem": "Build an adaptive multi-agent research system with strict reviewer gate",
        "candidates_file": str(REPO_ROOT / "examples/research-e2e-ai-case/plan/candidates.json"),
        "acceptance_file": str(REPO_ROOT / "examples/research-e2e-ai-case/plan/acceptance_spec.json"),
        "reports_dir": str(REPO_ROOT / "examples/research-e2e-ai-case/reports"),
        "max_rounds": 3,
        "max_review_cycles": 2,
        "strict_round_artifacts": True,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _run_pipeline() -> dict[str, Any]:
    run_root = _path_from_input(st.session_state.run_root)
    run_id = st.session_state.run_id.strip()
    problem = st.session_state.problem.strip()
    candidates_file = _path_from_input(st.session_state.candidates_file)
    acceptance_file = _path_from_input(st.session_state.acceptance_file)
    reports_dir = _path_from_input(st.session_state.reports_dir)

    if not candidates_file.exists():
        raise FileNotFoundError(f"candidates file not found: {candidates_file}")
    if not acceptance_file.exists():
        raise FileNotFoundError(f"acceptance file not found: {acceptance_file}")
    if not reports_dir.exists():
        raise FileNotFoundError(f"reports dir not found: {reports_dir}")

    summary = run_inbox_cycle(
        run_root=run_root,
        run_id=run_id,
        problem=problem,
        candidate_count=_candidate_count(candidates_file),
        max_rounds=int(st.session_state.max_rounds),
        max_review_cycles=int(st.session_state.max_review_cycles),
        reports_root=reports_dir,
        allow_fallback_rounds=not bool(st.session_state.strict_round_artifacts),
        auto_plan=False,
        candidates_file_input=candidates_file,
        acceptance_file_input=acceptance_file,
        debug_enabled=True,
        debug_console=False,
    )
    return summary


def main() -> None:
    st.set_page_config(page_title="Research Agent Team UI", layout="wide")
    _init_state()

    st.markdown(
        """
        <style>
        .agent-card {
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 10px 12px;
            background: #f9fafb;
        }
        .agent-role { font-weight: 700; font-size: 16px; }
        .agent-meta { color: #374151; font-size: 13px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("Research Agent Team Interactive UI")
    st.caption(
        "参考 learn-claude-code s09 的 Agent Team + Inbox 交互理念，展示角色协作、消息流、步骤级 I/O 调试。"
    )

    with st.sidebar:
        st.header("运行配置")
        st.text_input("Run Root", key="run_root")
        st.text_input("Run ID", key="run_id")
        st.text_area("Problem", key="problem", height=100)
        st.text_input("Candidates File", key="candidates_file")
        st.text_input("Acceptance File", key="acceptance_file")
        st.text_input("Reports Dir", key="reports_dir")
        st.number_input("Max Rounds", min_value=1, max_value=10, step=1, key="max_rounds")
        st.number_input("Max Review Cycles", min_value=1, max_value=10, step=1, key="max_review_cycles")
        st.checkbox("Strict Round Artifacts", key="strict_round_artifacts")

        col_a, col_b = st.columns(2)
        with col_a:
            run_clicked = st.button("运行 Team+Inbox", type="primary")
        with col_b:
            st.button("刷新视图")

    run_root = _path_from_input(st.session_state.run_root)
    run_id = st.session_state.run_id.strip()
    files = _run_files(run_root, run_id)

    if run_clicked:
        try:
            summary = _run_pipeline()
            st.success(
                f"运行完成: approved={summary.get('approved')} | winner={summary.get('winner_candidate')}"
            )
        except Exception as exc:
            st.error(str(exc))

    st.code(str(files.run_dir), language="text")

    messages = list_inbox_messages(files.run_dir)
    trace_payload = _load_trace_payload(files)
    events = _load_trace_events(files)
    team_rows = _team_stats(messages)

    tabs = st.tabs(["总览", "交互流程", "步骤调试 I/O", "通信线程", "Inbox 消息", "交付结果", "帮助"])

    with tabs[0]:
        st.subheader("运行总览")
        summary = _safe_json(files.pipeline_summary)
        review = _safe_json(files.review_feedback)
        conclusion = _safe_json(files.final_conclusion_json)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总消息数", len(messages))
        with col2:
            st.metric("调试事件数", len(events))
        with col3:
            approved = "-"
            if isinstance(summary, dict):
                approved = str(summary.get("approved", "-"))
            st.metric("评审通过", approved)
        with col4:
            winner = "-"
            if isinstance(summary, dict):
                winner = str(summary.get("winner_candidate", "-"))
            st.metric("最终胜出", winner)

        if isinstance(trace_payload, dict):
            trace_summary = trace_payload.get("summary", {})
            if isinstance(trace_summary, dict):
                col5, col6, col7 = st.columns(3)
                with col5:
                    st.metric("Trace Schema", str(trace_payload.get("schema_version", "-")))
                with col6:
                    st.metric("Trace Lanes", int(trace_payload.get("lane_count", 0) or 0))
                with col7:
                    st.metric("Open Calls", int(trace_summary.get("open_call_count", 0) or 0))

        if isinstance(review, dict):
            st.markdown("**Reviewer 输出**")
            st.json(review)

        if isinstance(conclusion, dict):
            st.markdown("**Final Conclusion**")
            st.json(conclusion)

        progress = _round_progress(files.run_dir)
        if progress:
            st.markdown("**候选方案轮次指标走势**")
            st.dataframe(progress, use_container_width=True, hide_index=True)

    with tabs[1]:
        st.subheader("智能体交互流程")
        if not messages:
            st.info("暂无消息。请先运行 Team+Inbox。")
        else:
            st.markdown("**角色看板（Leader + Workers + Reviewer）**")
            cols = st.columns(4)
            for idx, row in enumerate(team_rows):
                with cols[idx % 4]:
                    st.markdown(
                        "\n".join(
                            [
                                '<div class="agent-card">',
                                f'<div class="agent-role">{row["role"]}</div>',
                                f'<div class="agent-meta">sent: {row["sent"]}</div>',
                                f'<div class="agent-meta">received: {row["received"]}</div>',
                                f'<div class="agent-meta">last: {row["last_message"] or "-"}</div>',
                                "</div>",
                            ]
                        ),
                        unsafe_allow_html=True,
                    )

            st.markdown("**Agent Team 消息流图**")
            st.graphviz_chart(_build_graphviz(messages), use_container_width=True)

            st.markdown("**边统计**")
            st.dataframe(_edge_rows(messages), use_container_width=True, hide_index=True)

    with tabs[2]:
        _render_event_detail(events, trace_payload)

    with tabs[3]:
        _render_thread_diagnostics(files, messages)

    with tabs[4]:
        st.subheader("Inbox 消息浏览")
        if not messages:
            st.info("暂无 Inbox 消息。")
        else:
            roles = sorted({str(row.get("_inbox_role", "")).strip() for row in messages if str(row.get("_inbox_role", "")).strip()})
            types = sorted({str(row.get("type", "")).strip() for row in messages if str(row.get("type", "")).strip()})
            rounds = sorted({int(row.get("round", 0) or 0) for row in messages if isinstance(row.get("round", 0), int)})

            role_pick = st.selectbox("角色过滤", ["(all)"] + roles)
            type_pick = st.selectbox("类型过滤", ["(all)"] + types)
            round_pick = st.selectbox("轮次过滤", ["(all)"] + [str(value) for value in rounds])

            filtered: list[dict[str, Any]] = []
            for row in messages:
                if role_pick != "(all)" and str(row.get("_inbox_role", "")) != role_pick:
                    continue
                if type_pick != "(all)" and str(row.get("type", "")) != type_pick:
                    continue
                if round_pick != "(all)" and int(row.get("round", -1) or -1) != int(round_pick):
                    continue
                filtered.append(row)

            view_rows: list[dict[str, Any]] = []
            for row in filtered:
                payload = row.get("payload", {}) if isinstance(row.get("payload"), dict) else {}
                view_rows.append(
                    {
                        "ts_utc": row.get("ts_utc", ""),
                        "round": row.get("round", ""),
                        "from": row.get("from", ""),
                        "to": row.get("to", ""),
                        "type": row.get("type", ""),
                        "correlation_id": row.get("correlation_id", ""),
                        "payload_keys": ",".join(sorted(payload.keys())),
                        "id": row.get("id", ""),
                    }
                )

            st.metric("消息数", len(view_rows))
            st.dataframe(view_rows, use_container_width=True, hide_index=True)

            msg_id = st.text_input("输入消息 ID 查看详情")
            if msg_id.strip():
                matched = [row for row in filtered if str(row.get("id", "")).strip() == msg_id.strip()]
                if matched:
                    st.json(matched[0])
                else:
                    st.warning("未找到该消息 ID。")

    with tabs[5]:
        st.subheader("交付结果")
        for title, path in [
            ("pipeline_summary_inbox.json", files.pipeline_summary),
            ("final_conclusion_inbox.json", files.final_conclusion_json),
            ("review_feedback.json", files.review_feedback),
            ("runtime_trace_health.json", files.trace_health_json),
            ("message_threads.json", files.message_threads_json),
        ]:
            st.markdown(f"**{title}**")
            payload = _safe_json(path)
            if payload is None:
                st.info(f"未找到: {path}")
            else:
                st.json(payload)

        st.markdown("**runtime_trace.md**")
        if files.trace_md.exists():
            st.code(files.trace_md.read_text(encoding="utf-8"), language="markdown")
        else:
            st.info("未找到 runtime_trace.md")

    with tabs[6]:
        st.subheader("说明")
        st.write("1. 推荐先用 CLI 跑 `run_inbox_cycle.py`，再用本 UI 做交互分析。")
        st.write("2. 步骤调试页读取 `debug/runtime_trace.json`，支持 lane/call_id/message_id 过滤。")
        st.write("3. 通信线程页读取 `debug/message_threads.json`，可定位孤儿 reply 与线程密度。")
        st.write("4. 若要模拟 learn-claude-code 的 Team 协作观感，重点看“交互流程”与“通信线程”页签。")
        st.code("streamlit run apps/research_team_interactive_ui.py", language="bash")


if __name__ == "__main__":
    main()
