from __future__ import annotations

import argparse
import json
from pathlib import Path

from inbox_lib import send_message


def _payload_from_args(payload_json: str, payload_file: str) -> dict:
    if payload_json.strip() and payload_file.strip():
        raise ValueError("Use either --payload-json or --payload-file, not both.")

    if payload_json.strip():
        data = json.loads(payload_json)
        if not isinstance(data, dict):
            raise ValueError("--payload-json must decode to a JSON object.")
        return data

    if payload_file.strip():
        path = Path(payload_file)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("--payload-file must contain a JSON object.")
        return data

    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Send one structured inbox message.")
    parser.add_argument("--inbox-root", required=True, help="Inbox root dir (e.g., <run_dir>/runtime/inbox).")
    parser.add_argument("--run-id", required=True, help="Run id.")
    parser.add_argument("--round", required=True, type=int, help="Round index.")
    parser.add_argument("--from", required=True, dest="from_role", help="Sender role.")
    parser.add_argument("--to", required=True, dest="to_role", help="Receiver role.")
    parser.add_argument("--type", required=True, dest="message_type", help="Message type.")
    parser.add_argument("--correlation-id", required=True, help="Task correlation id.")
    parser.add_argument("--reply-to", default="", help="Optional reply-to message id.")
    parser.add_argument("--priority", default="normal", help="Message priority.")
    parser.add_argument("--payload-json", default="", help="Inline JSON object payload.")
    parser.add_argument("--payload-file", default="", help="Path to payload JSON object file.")
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="Artifact path (repeatable).",
    )
    parser.add_argument("--output", default="", help="Optional output path for emitted message JSON.")
    args = parser.parse_args()

    payload = _payload_from_args(args.payload_json, args.payload_file)

    message = send_message(
        inbox_root=Path(args.inbox_root),
        run_id=args.run_id,
        round_index=args.round,
        from_role=args.from_role,
        to_role=args.to_role,
        message_type=args.message_type,
        correlation_id=args.correlation_id,
        payload=payload,
        reply_to=args.reply_to,
        priority=args.priority,
        artifacts=args.artifact,
    )

    text = json.dumps(message, indent=2, ensure_ascii=False) + "\n"
    if args.output.strip():
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
