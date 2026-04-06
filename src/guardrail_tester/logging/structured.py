from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StructuredLogger:
    """JSON-lines logger for guardrail testing events."""

    def __init__(self, log_dir: str | Path | None = None, run_id: str | None = None):
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._events: list[dict[str, Any]] = []

        if log_dir:
            self.log_dir = Path(log_dir)
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.log_file = self.log_dir / f"run_{self.run_id}.jsonl"
        else:
            self.log_dir = None
            self.log_file = None

    def _emit(self, event: dict[str, Any]) -> None:
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        event["run_id"] = self.run_id
        self._events.append(event)

        if self.log_file:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(event, default=str) + "\n")

    def log_input(self, user_input: str, metadata: dict[str, Any] | None = None) -> None:
        self._emit({
            "event": "input",
            "content": user_input,
            "metadata": metadata or {},
        })

    def log_output(self, output: str, metadata: dict[str, Any] | None = None) -> None:
        self._emit({
            "event": "output",
            "content": output,
            "metadata": metadata or {},
        })

    def log_guardrail_check(
        self,
        guardrail_name: str,
        layer: str,
        passed: bool,
        action: str,
        message: str = "",
        latency_ms: float = 0.0,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._emit({
            "event": "guardrail_check",
            "guardrail_name": guardrail_name,
            "layer": layer,
            "passed": passed,
            "action": action,
            "message": message,
            "latency_ms": round(latency_ms, 2),
            "details": details or {},
        })

    def log_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        phase: str = "pre",
        result: str | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "event": "tool_call",
            "tool_name": tool_name,
            "tool_args": tool_args,
            "phase": phase,
        }
        if result is not None:
            event["result"] = result[:2000]
        self._emit(event)

    def log_agent_step(self, step: str, details: dict[str, Any] | None = None) -> None:
        self._emit({
            "event": "agent_step",
            "step": step,
            "details": details or {},
        })

    def log_error(self, error: str, details: dict[str, Any] | None = None) -> None:
        self._emit({
            "event": "error",
            "error": error,
            "details": details or {},
        })

    def log_scenario_result(
        self,
        scenario_id: str,
        passed: bool,
        expected_outcome: str,
        actual_outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._emit({
            "event": "scenario_result",
            "scenario_id": scenario_id,
            "passed": passed,
            "expected_outcome": expected_outcome,
            "actual_outcome": actual_outcome,
            "details": details or {},
        })

    @property
    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def get_guardrail_events(self) -> list[dict[str, Any]]:
        return [e for e in self._events if e["event"] == "guardrail_check"]

    def get_tool_events(self) -> list[dict[str, Any]]:
        return [e for e in self._events if e["event"] == "tool_call"]


_default_logger: StructuredLogger | None = None


def get_logger(name: str | None = None) -> StructuredLogger:
    global _default_logger
    if _default_logger is None:
        _default_logger = StructuredLogger()
    return _default_logger


def init_logger(log_dir: str | Path | None = None, run_id: str | None = None) -> StructuredLogger:
    global _default_logger
    _default_logger = StructuredLogger(log_dir=log_dir, run_id=run_id)
    return _default_logger
