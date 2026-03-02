"""
Observability — structured logging and trace export for the QA agent pipeline.

Provides:
  - TraceLog: records every node entry/exit, token usage, cost, and errors
  - Exportable as JSON for debugging, analysis, and cost accounting
  - Integration with agent nodes via context passing

Production considerations:
  - Every VLM call is logged with input/output tokens and USD cost
  - Retry events are tracked to measure cost of error recovery
  - Full trace enables post-hoc debugging of any extraction failure
"""
from __future__ import annotations

import time
import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class TraceEvent:
    """A single event in the agent trace log."""
    timestamp: float
    node: str
    event_type: str  # "enter", "exit", "error", "retry", "info"
    message: str = ""
    data: dict[str, Any] | None = None
    duration_s: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


@dataclass
class TraceLog:
    """
    Full trace of an agent execution.

    Records every step, VLM call, validation error, and retry.
    Provides cost rollup and timing analysis.
    """
    image_path: str = ""
    events: list[TraceEvent] = field(default_factory=list)
    _node_starts: dict[str, float] = field(default_factory=dict, repr=False)

    def enter_node(self, node: str, message: str = "", data: dict | None = None) -> None:
        """Record entry into a graph node."""
        now = time.time()
        self._node_starts[node] = now
        self.events.append(TraceEvent(
            timestamp=now,
            node=node,
            event_type="enter",
            message=message or f"Entering {node}",
            data=data,
        ))

    def exit_node(
        self,
        node: str,
        message: str = "",
        data: dict | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd: float | None = None,
    ) -> None:
        """Record exit from a graph node."""
        now = time.time()
        start = self._node_starts.pop(node, now)
        duration = now - start
        self.events.append(TraceEvent(
            timestamp=now,
            node=node,
            event_type="exit",
            message=message or f"Exiting {node}",
            data=data,
            duration_s=round(duration, 3),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        ))

    def log_error(self, node: str, error: str, data: dict | None = None) -> None:
        """Record an error event."""
        self.events.append(TraceEvent(
            timestamp=time.time(),
            node=node,
            event_type="error",
            message=error,
            data=data,
        ))

    def log_retry(self, node: str, attempt: int, reason: str) -> None:
        """Record a retry event."""
        self.events.append(TraceEvent(
            timestamp=time.time(),
            node=node,
            event_type="retry",
            message=f"Retry attempt {attempt}: {reason}",
            data={"attempt": attempt, "reason": reason},
        ))

    def log_info(self, node: str, message: str, data: dict | None = None) -> None:
        """Record an informational event."""
        self.events.append(TraceEvent(
            timestamp=time.time(),
            node=node,
            event_type="info",
            message=message,
            data=data,
        ))

    # ── Aggregation methods ───────────────────────────────────

    @property
    def total_cost_usd(self) -> float:
        """Sum of all VLM call costs."""
        return sum(e.cost_usd for e in self.events if e.cost_usd is not None)

    @property
    def total_input_tokens(self) -> int:
        """Sum of all input tokens across VLM calls."""
        return sum(e.input_tokens for e in self.events if e.input_tokens is not None)

    @property
    def total_output_tokens(self) -> int:
        """Sum of all output tokens across VLM calls."""
        return sum(e.output_tokens for e in self.events if e.output_tokens is not None)

    @property
    def total_duration_s(self) -> float:
        """Total pipeline execution time."""
        if not self.events:
            return 0.0
        return self.events[-1].timestamp - self.events[0].timestamp

    @property
    def retry_count(self) -> int:
        """Number of retry events."""
        return sum(1 for e in self.events if e.event_type == "retry")

    @property
    def error_count(self) -> int:
        """Number of error events."""
        return sum(1 for e in self.events if e.event_type == "error")

    @property
    def vlm_call_count(self) -> int:
        """Number of VLM calls (nodes that exit with token usage)."""
        return sum(1 for e in self.events if e.event_type == "exit" and e.input_tokens is not None)

    def summary(self) -> dict:
        """Compact summary for reporting."""
        return {
            "image_path": self.image_path,
            "total_duration_s": round(self.total_duration_s, 3),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "vlm_calls": self.vlm_call_count,
            "retries": self.retry_count,
            "errors": self.error_count,
            "node_count": len(set(e.node for e in self.events)),
        }

    def to_dict(self) -> dict:
        """Full trace as a serializable dict."""
        return {
            "image_path": self.image_path,
            "summary": self.summary(),
            "events": [asdict(e) for e in self.events],
        }

    def to_json(self, indent: int = 2) -> str:
        """Full trace as JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def print_timeline(self) -> None:
        """Print a human-readable timeline to stdout."""
        if not self.events:
            print("  (empty trace)")
            return

        base = self.events[0].timestamp
        for e in self.events:
            t = e.timestamp - base
            cost_str = f" ${e.cost_usd:.5f}" if e.cost_usd else ""
            tok_str = f" [{e.input_tokens}+{e.output_tokens} tok]" if e.input_tokens else ""
            dur_str = f" ({e.duration_s:.2f}s)" if e.duration_s else ""
            print(f"  [{t:6.2f}s] {e.event_type:>6} {e.node:<15} {e.message}{dur_str}{tok_str}{cost_str}")
