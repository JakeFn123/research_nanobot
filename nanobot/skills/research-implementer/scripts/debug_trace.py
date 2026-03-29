from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class DebugTrace:
    run_dir: Path
    enabled: bool = True
    console: bool = False

    def __post_init__(self) -> None:
        self.index = 0
        self.debug_dir = self.run_dir / "debug"
        self.jsonl_path = self.debug_dir / "runtime_trace.jsonl"
        self.md_path = self.debug_dir / "runtime_trace.md"

        if not self.enabled:
            return

        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path.write_text("", encoding="utf-8")
        self.md_path.write_text(
            "# Runtime Trace\n\n"
            "| # | time_utc | status | step | message | details |\n"
            "|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )

    def log(
        self,
        *,
        step: str,
        status: str,
        message: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return

        self.index += 1
        payload = {
            "index": self.index,
            "time_utc": _utc_now(),
            "status": status,
            "step": step,
            "message": message,
            "details": details or {},
        }

        with self.jsonl_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")

        details_text = json.dumps(payload["details"], ensure_ascii=False)
        safe_message = message.replace("|", "/")
        safe_step = step.replace("|", "/")
        safe_details = details_text.replace("|", "/")
        with self.md_path.open("a", encoding="utf-8") as fp:
            fp.write(
                f"| {payload['index']} | {payload['time_utc']} | {status} | {safe_step} | {safe_message} | {safe_details} |\n"
            )

        if self.console:
            print(
                f"[trace#{payload['index']}] [{status}] {step} - {message} | details={details_text}",
                flush=True,
            )

    def paths(self) -> dict[str, str]:
        return {
            "jsonl": str(self.jsonl_path),
            "markdown": str(self.md_path),
        }
