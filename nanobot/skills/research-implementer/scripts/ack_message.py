from __future__ import annotations

import argparse
import json
from pathlib import Path

from inbox_lib import ack_messages, read_inbox


def main() -> int:
    parser = argparse.ArgumentParser(description="Ack inbox messages for one role.")
    parser.add_argument("--inbox-root", required=True, help="Inbox root dir (e.g., <run_dir>/runtime/inbox).")
    parser.add_argument("--role", required=True, help="Role inbox.")
    parser.add_argument("--message-id", action="append", default=[], help="Message id to ack (repeatable).")
    parser.add_argument("--all-visible", action="store_true", help="Ack currently visible unacked messages.")
    parser.add_argument("--run-id", default="", help="Optional run filter when using --all-visible.")
    parser.add_argument("--round", type=int, default=-1, help="Optional round filter when using --all-visible.")
    parser.add_argument("--type", dest="message_type", default="", help="Optional type filter when using --all-visible.")
    parser.add_argument("--actor", default="", help="Ack actor (defaults to role).")
    parser.add_argument("--reason", default="", help="Ack reason.")
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    args = parser.parse_args()

    message_ids = [item.strip() for item in args.message_id if item.strip()]

    if args.all_visible:
        rows = read_inbox(
            inbox_root=Path(args.inbox_root),
            role=args.role,
            limit=100000,
            include_acked=False,
            run_id=args.run_id.strip() or None,
            round_index=args.round if args.round >= 0 else None,
            message_type=args.message_type.strip() or None,
            correlation_id=None,
            drain=False,
        )
        message_ids.extend([str(row.get("id", "")).strip() for row in rows if str(row.get("id", "")).strip()])

    if not message_ids:
        raise ValueError("No message ids selected. Use --message-id or --all-visible.")

    ack_rows = ack_messages(
        inbox_root=Path(args.inbox_root),
        role=args.role,
        message_ids=message_ids,
        actor=args.actor,
        reason=args.reason,
    )

    text = json.dumps(ack_rows, indent=2, ensure_ascii=False) + "\n"
    if args.output.strip():
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
