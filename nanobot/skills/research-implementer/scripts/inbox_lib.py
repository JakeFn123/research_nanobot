from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

REQUIRED_ENVELOPE_FIELDS = {
    "id",
    "run_id",
    "round",
    "from",
    "to",
    "type",
    "correlation_id",
    "ts_utc",
    "payload",
}

ROLE_RE = re.compile(r"^[a-z0-9_]+$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_role(value: str) -> str:
    role = value.strip().lower()
    if not role or not ROLE_RE.match(role):
        raise ValueError(f"Invalid role '{value}'. Use lowercase letters, digits, underscore only.")
    return role


def _jsonl_append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def _jsonl_read(path: Path) -> list[dict[str, Any]]:
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


def inbox_file(inbox_root: Path, role: str) -> Path:
    return inbox_root / f"{_safe_role(role)}.jsonl"


def ack_file(inbox_root: Path, role: str) -> Path:
    return inbox_root / "_acks" / f"{_safe_role(role)}.jsonl"


def _validate_envelope(message: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_ENVELOPE_FIELDS - set(message))
    if missing:
        raise ValueError(f"Message envelope missing required fields: {', '.join(missing)}")

    if not isinstance(message["id"], str) or not message["id"].strip():
        raise ValueError("Message 'id' must be a non-empty string.")
    if not isinstance(message["run_id"], str) or not message["run_id"].strip():
        raise ValueError("Message 'run_id' must be a non-empty string.")

    round_value = message["round"]
    if not isinstance(round_value, int) or round_value < 0:
        raise ValueError("Message 'round' must be an integer >= 0.")

    _safe_role(str(message["from"]))
    _safe_role(str(message["to"]))

    if not isinstance(message["type"], str) or not message["type"].strip():
        raise ValueError("Message 'type' must be a non-empty string.")
    if not isinstance(message["correlation_id"], str) or not message["correlation_id"].strip():
        raise ValueError("Message 'correlation_id' must be a non-empty string.")

    if not isinstance(message["payload"], dict):
        raise ValueError("Message 'payload' must be a JSON object.")


def send_message(
    *,
    inbox_root: Path,
    run_id: str,
    round_index: int,
    from_role: str,
    to_role: str,
    message_type: str,
    correlation_id: str,
    payload: dict[str, Any] | None = None,
    reply_to: str = "",
    call_id: str = "",
    thread_id: str = "",
    priority: str = "normal",
    artifacts: list[str] | None = None,
) -> dict[str, Any]:
    from_norm = _safe_role(from_role)
    to_norm = _safe_role(to_role)

    message = {
        "id": f"msg_{uuid4().hex}",
        "run_id": run_id.strip(),
        "round": int(round_index),
        "from": from_norm,
        "to": to_norm,
        "type": message_type.strip(),
        "priority": (priority.strip() or "normal").lower(),
        "call_id": call_id.strip() or f"call_{uuid4().hex[:16]}",
        "correlation_id": correlation_id.strip(),
        "thread_id": thread_id.strip() or correlation_id.strip(),
        "reply_to": reply_to.strip(),
        "ts_utc": _utc_now(),
        "payload": payload or {},
        "artifacts": [item for item in (artifacts or []) if isinstance(item, str) and item.strip()],
    }
    _validate_envelope(message)
    _jsonl_append(inbox_file(inbox_root, to_norm), message)
    return message


def _load_acked_ids(inbox_root: Path, role: str) -> set[str]:
    ack_rows = _jsonl_read(ack_file(inbox_root, role))
    out: set[str] = set()
    for row in ack_rows:
        msg_id = row.get("message_id")
        if isinstance(msg_id, str) and msg_id.strip():
            out.add(msg_id.strip())
    return out


def ack_messages(
    *,
    inbox_root: Path,
    role: str,
    message_ids: list[str],
    actor: str = "",
    reason: str = "",
) -> list[dict[str, Any]]:
    role_norm = _safe_role(role)
    rows: list[dict[str, Any]] = []
    for msg_id in message_ids:
        clean = msg_id.strip()
        if not clean:
            continue
        row = {
            "message_id": clean,
            "acked_by": _safe_role(actor) if actor.strip() else role_norm,
            "reason": reason.strip(),
            "ts_utc": _utc_now(),
        }
        _jsonl_append(ack_file(inbox_root, role_norm), row)
        rows.append(row)
    return rows


def read_inbox(
    *,
    inbox_root: Path,
    role: str,
    limit: int = 50,
    include_acked: bool = False,
    run_id: str | None = None,
    round_index: int | None = None,
    message_type: str | None = None,
    correlation_id: str | None = None,
    drain: bool = False,
) -> list[dict[str, Any]]:
    role_norm = _safe_role(role)
    rows = _jsonl_read(inbox_file(inbox_root, role_norm))
    acked = set() if include_acked else _load_acked_ids(inbox_root, role_norm)

    out: list[dict[str, Any]] = []
    for row in rows:
        msg_id = str(row.get("id", "")).strip()
        if not msg_id:
            continue
        if msg_id in acked:
            continue
        if run_id is not None and str(row.get("run_id", "")) != run_id:
            continue
        if round_index is not None and int(row.get("round", -1) or -1) != round_index:
            continue
        if message_type is not None and str(row.get("type", "")) != message_type:
            continue
        if correlation_id is not None and str(row.get("correlation_id", "")) != correlation_id:
            continue

        out.append(row)
        if len(out) >= max(1, limit):
            break

    if drain and out:
        ack_messages(
            inbox_root=inbox_root,
            role=role_norm,
            message_ids=[str(row.get("id", "")).strip() for row in out],
            actor=role_norm,
            reason="drain",
        )

    return out


def list_inbox_messages(run_dir: Path) -> list[dict[str, Any]]:
    inbox_root = run_dir / "runtime" / "inbox"
    if not inbox_root.exists():
        return []

    rows: list[dict[str, Any]] = []
    for file_path in sorted(inbox_root.glob("*.jsonl")):
        role = file_path.stem
        for row in _jsonl_read(file_path):
            row_copy = dict(row)
            row_copy.setdefault("_inbox_role", role)
            rows.append(row_copy)

    rows.sort(key=lambda item: (str(item.get("ts_utc", "")), str(item.get("id", ""))))
    return rows
