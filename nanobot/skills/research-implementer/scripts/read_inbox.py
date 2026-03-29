from __future__ import annotations

import argparse
import json
from pathlib import Path

from inbox_lib import read_inbox


def main() -> int:
    parser = argparse.ArgumentParser(description="Read messages from one role inbox.")
    parser.add_argument("--inbox-root", required=True, help="Inbox root dir (e.g., <run_dir>/runtime/inbox).")
    parser.add_argument("--role", required=True, help="Role inbox to read.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum returned messages.")
    parser.add_argument("--include-acked", action="store_true", help="Include already acked messages.")
    parser.add_argument("--run-id", default="", help="Optional run_id filter.")
    parser.add_argument("--round", type=int, default=-1, help="Optional round filter.")
    parser.add_argument("--type", dest="message_type", default="", help="Optional message type filter.")
    parser.add_argument("--correlation-id", default="", help="Optional correlation id filter.")
    parser.add_argument("--drain", action="store_true", help="Ack returned messages immediately.")
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    args = parser.parse_args()

    rows = read_inbox(
        inbox_root=Path(args.inbox_root),
        role=args.role,
        limit=max(1, args.limit),
        include_acked=args.include_acked,
        run_id=args.run_id.strip() or None,
        round_index=args.round if args.round >= 0 else None,
        message_type=args.message_type.strip() or None,
        correlation_id=args.correlation_id.strip() or None,
        drain=args.drain,
    )

    text = json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
    if args.output.strip():
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
