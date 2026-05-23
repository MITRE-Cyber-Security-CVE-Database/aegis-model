"""Base agent adapter for AutoBench. Adapters convert tasks into agent invocations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentResponse:
    """Standardized output every adapter must return."""
    trace: list  # list of TraceEvent (or dict serializations)
    final_message: str
    tokens_used: int = 0
    wall_time_s: float = 0.0


class AgentAdapter(ABC):
    """Adapter interface. Every agent (Claude, GPT, Ollama, local) implements this."""

    name: str = "base"

    @abstractmethod
    def run_task(self, task_spec: dict, work_dir: str) -> AgentResponse:
        """
        Receive a task spec, execute it autonomously, return trace + result.

        Hard rule: implementations MUST NOT solicit human input mid-run.
        Any request for clarification should be logged as a 'human_help' trace event.
        """
        raise NotImplementedError
