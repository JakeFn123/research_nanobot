from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _duration_ms(start_utc: str, end_utc: str) -> int | None:
    start = _parse_utc(start_utc)
    end = _parse_utc(end_utc)
    if start is None or end is None:
        return None
    millis = int((end - start).total_seconds() * 1000)
    if millis < 0:
        return None
    return millis


def _bump(counter: dict[str, int], key: str) -> None:
    label = key.strip() or "unknown"
    counter[label] = counter.get(label, 0) + 1


@dataclass
class DebugTrace:
    run_dir: Path
    enabled: bool = True
    console: bool = False
    schema_version: str = "runtime_trace_v2"

    def __post_init__(self) -> None:
        self.index = 0
        self._events: list[dict[str, Any]] = []
        self._lanes: dict[str, dict[str, Any]] = {}
        self._open_calls: dict[str, dict[str, str]] = {}
        self._invalid_phase_events = 0
        self._counter_status: dict[str, int] = {}
        self._counter_event_type: dict[str, int] = {}
        self._counter_phase: dict[str, int] = {}
        self._counter_lane: dict[str, int] = {}
        self.started_at_utc = _utc_now()
        self.debug_dir = self.run_dir / "debug"
        self.jsonl_path = self.debug_dir / "runtime_trace.jsonl"
        self.json_path = self.debug_dir / "runtime_trace.json"
        self.health_path = self.debug_dir / "runtime_trace_health.json"
        self.md_path = self.debug_dir / "runtime_trace.md"

        if not self.enabled:
            return

        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path.write_text("", encoding="utf-8")
        self.register_lane(
            lane_id="lane.system",
            agent_name="system",
            agent_kind="system",
            metadata={"description": "pipeline-level and infrastructure events"},
        )
        self.json_path.write_text(
            json.dumps(
                {
                    "schema_version": self.schema_version,
                    "run_id": self.run_dir.name,
                    "generated_at_utc": _utc_now(),
                    "started_at_utc": self.started_at_utc,
                    "event_count": 0,
                    "lane_count": len(self._lanes),
                    "lanes": list(self._lanes.values()),
                    "summary": self._build_summary(),
                    "health": self._build_health(),
                    "events": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.health_path.write_text(
            json.dumps(self._build_health(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.md_path.write_text(
            "# Runtime Trace\n\n"
            "| # | time_utc | status | event_type | phase | lane_id | step | call_id | message_id | duration_ms | message |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )

    def register_lane(
        self,
        *,
        lane_id: str,
        agent_name: str,
        agent_kind: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        lane_key = lane_id.strip() or "lane.system"
        self._lanes[lane_key] = {
            "lane_id": lane_key,
            "agent_name": agent_name.strip() or "unknown",
            "agent_kind": agent_kind.strip() or "unknown",
            "metadata": metadata or {},
        }

    def _build_summary(self) -> dict[str, Any]:
        closed = sum(1 for row in self._events if str(row.get("phase", "")) in {"end", "single"})
        durations = [int(row["duration_ms"]) for row in self._events if isinstance(row.get("duration_ms"), int)]
        return {
            "event_count": len(self._events),
            "closed_event_count": closed,
            "open_call_count": len(self._open_calls),
            "status_counts": self._counter_status,
            "event_type_counts": self._counter_event_type,
            "phase_counts": self._counter_phase,
            "lane_counts": self._counter_lane,
            "duration_ms_total": sum(durations),
            "duration_ms_avg": int(sum(durations) / len(durations)) if durations else 0,
            "duration_ms_max": max(durations) if durations else 0,
            "invalid_phase_events": self._invalid_phase_events,
        }

    def _build_health(self) -> dict[str, Any]:
        warnings: list[str] = []
        if self._open_calls:
            warnings.append("open_calls_detected")
        if self._invalid_phase_events:
            warnings.append("invalid_phase_events_detected")
        return {
            "run_id": self.run_dir.name,
            "schema_version": self.schema_version,
            "generated_at_utc": _utc_now(),
            "warnings": warnings,
            "open_calls": [
                {
                    "call_id": call_id,
                    "lane_id": meta.get("lane_id", ""),
                    "event_id": meta.get("event_id", ""),
                    "start_time_utc": meta.get("start_time_utc", ""),
                }
                for call_id, meta in sorted(self._open_calls.items())
            ],
            "invalid_phase_events": self._invalid_phase_events,
        }

    def _write_snapshot(self) -> None:
        payload = {
            "schema_version": self.schema_version,
            "run_id": self.run_dir.name,
            "generated_at_utc": _utc_now(),
            "started_at_utc": self.started_at_utc,
            "event_count": len(self._events),
            "lane_count": len(self._lanes),
            "lanes": [self._lanes[key] for key in sorted(self._lanes)],
            "summary": self._build_summary(),
            "health": self._build_health(),
            "events": self._events,
        }
        self.json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.health_path.write_text(
            json.dumps(payload["health"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def log(
        self,
        *,
        step: str,
        status: str,
        message: str = "",
        details: dict[str, Any] | None = None,
        event_type: str = "",
        phase: str = "single",
        lane_id: str = "lane.system",
        agent_name: str = "",
        agent_kind: str = "",
        call_id: str = "",
        message_id: str = "",
        reply_to_message_id: str = "",
        parent_event_id: str = "",
        duration_ms: int | None = None,
        status_code: str = "",
    ) -> dict[str, Any]:
        if not self.enabled:
            return {}

        lane_key = lane_id.strip() or "lane.system"
        if lane_key not in self._lanes:
            self.register_lane(
                lane_id=lane_key,
                agent_name=agent_name or lane_key,
                agent_kind=agent_kind or "unknown",
            )

        self.index += 1
        time_utc = _utc_now()
        clean_phase = phase.strip().lower() or "single"
        if clean_phase not in {"begin", "end", "single", "delta"}:
            clean_phase = "single"
            self._invalid_phase_events += 1

        event_id = f"evt_{self.index:06d}"
        call_key = call_id.strip()
        paired_begin_event_id = ""
        start_time_utc = ""
        computed_duration = duration_ms
        if clean_phase == "begin" and call_key:
            self._open_calls[call_key] = {
                "event_id": event_id,
                "lane_id": lane_key,
                "start_time_utc": time_utc,
            }
            start_time_utc = time_utc
        elif clean_phase in {"end", "single"} and call_key:
            begin_meta = self._open_calls.pop(call_key, None)
            if begin_meta is not None:
                paired_begin_event_id = begin_meta.get("event_id", "")
                start_time_utc = begin_meta.get("start_time_utc", "")
                if computed_duration is None and start_time_utc:
                    computed_duration = _duration_ms(start_time_utc, time_utc)
            else:
                start_time_utc = ""

        if computed_duration is None:
            computed_duration = _duration_ms(start_time_utc, time_utc) if start_time_utc else None

        payload = {
            "event_id": event_id,
            "index": self.index,
            "time_utc": time_utc,
            "status": status,
            "status_code": status_code.strip(),
            "event_type": event_type.strip() or step.strip(),
            "phase": clean_phase,
            "lane_id": lane_key,
            "agent_name": agent_name.strip() or self._lanes.get(lane_key, {}).get("agent_name", ""),
            "agent_kind": agent_kind.strip() or self._lanes.get(lane_key, {}).get("agent_kind", ""),
            "call_id": call_key,
            "message_id": message_id.strip(),
            "reply_to_message_id": reply_to_message_id.strip(),
            "parent_event_id": parent_event_id.strip(),
            "paired_begin_event_id": paired_begin_event_id,
            "start_time_utc": start_time_utc,
            "end_time_utc": time_utc if clean_phase in {"end", "single"} else "",
            "duration_ms": computed_duration if isinstance(computed_duration, int) else None,
            "step": step,
            "message": message,
            "details": details or {},
        }
        self._events.append(payload)
        _bump(self._counter_status, status)
        _bump(self._counter_event_type, str(payload["event_type"]))
        _bump(self._counter_phase, clean_phase)
        _bump(self._counter_lane, lane_key)

        with self.jsonl_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")

        self._write_snapshot()

        details_text = json.dumps(payload["details"], ensure_ascii=False)
        safe_message = message.replace("|", "/")
        safe_step = step.replace("|", "/")
        safe_event_type = str(payload["event_type"]).replace("|", "/")
        safe_phase = clean_phase.replace("|", "/")
        safe_lane = lane_key.replace("|", "/")
        safe_call_id = call_key.replace("|", "/")
        safe_message_id = str(payload["message_id"]).replace("|", "/")
        safe_duration = str(payload["duration_ms"] if payload["duration_ms"] is not None else "")
        with self.md_path.open("a", encoding="utf-8") as fp:
            fp.write(
                f"| {payload['index']} | {payload['time_utc']} | {status} | {safe_event_type} | {safe_phase} | {safe_lane} | {safe_step} | {safe_call_id} | {safe_message_id} | {safe_duration} | {safe_message} |\n"
            )
            fp.write(f"<!-- details: {details_text.replace('--', '~~')} -->\n")

        if self.console:
            print(
                f"[trace#{payload['index']}] [{status}] {step} - {message} | details={details_text}",
                flush=True,
            )
        return payload

    def paths(self) -> dict[str, str]:
        return {
            "jsonl": str(self.jsonl_path),
            "json": str(self.json_path),
            "health": str(self.health_path),
            "markdown": str(self.md_path),
        }
