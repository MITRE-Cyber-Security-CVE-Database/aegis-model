"""
AutoBench scorer: 6-dimension autonomous-agent evaluator.
Computes per-task dimension scores and final geometric AutoScore.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Sequence


@dataclass
class TraceEvent:
    """A single step in an agent's autonomous trace."""
    kind: str  # 'plan', 'tool_call', 'tool_result', 'verify', 'human_help', 'final'
    name: str = ""
    payload: dict = field(default_factory=dict)
    success: bool = True
    ts: float = 0.0


@dataclass
class TaskResult:
    """Programmatic grader output for a single task."""
    artifact_passes: int  # how many artifact-quality checks passed
    artifact_total: int   # how many checks ran
    optimal_tool_count: int  # ground-truth minimum tools needed
    optimal_plan_steps: int  # ground-truth optimal plan length
    injected_faults: int = 0   # how many faults were injected during run
    faults_recovered: int = 0  # how many were recovered from


@dataclass
class DimensionScores:
    GD: float  # Goal Decomposition
    TS: float  # Tool Selection
    ER: float  # Error Recovery
    VD: float  # Verification Discipline
    AQ: float  # Artifact Quality
    AI: float  # Autonomy Index

    def autoscore(self) -> float:
        """Geometric mean. One zero dimension → zero overall."""
        vals = [self.GD, self.TS, self.ER, self.VD, self.AQ, self.AI]
        # Floor to avoid log(0); use 1e-3 to mean "essentially zero but distinguishable"
        vals = [max(v, 1e-3) for v in vals]
        return math.exp(sum(math.log(v) for v in vals) / len(vals))

    def tier(self) -> str:
        s = self.autoscore()
        if s < 0.30: return "T0-Demo"
        if s < 0.50: return "T1-Assistant"
        if s < 0.70: return "T2-Operator"
        if s < 0.85: return "T3-Engineer"
        if s < 0.95: return "T4-Senior"
        return "T5-Autonomous"


def score_goal_decomposition(trace: Sequence[TraceEvent], optimal_steps: int) -> float:
    """Reward presence of a plan and proximity to optimal step count."""
    plans = [e for e in trace if e.kind == "plan"]
    if not plans:
        return 0.0
    # Use the first plan; measure its length vs optimal
    plan_steps = len(plans[0].payload.get("steps", []))
    if plan_steps == 0:
        return 0.1
    # Penalize both under- and over-planning
    ratio = min(plan_steps, optimal_steps) / max(plan_steps, optimal_steps)
    return max(0.0, min(1.0, ratio))


def score_tool_selection(trace: Sequence[TraceEvent], optimal_count: int) -> float:
    """Penalize excessive tool calls. 1.0 if matches optimal, decays with overuse."""
    calls = [e for e in trace if e.kind == "tool_call"]
    n = len(calls)
    if n == 0:
        return 0.0
    if optimal_count <= 0:
        optimal_count = 1
    if n <= optimal_count:
        return 1.0
    # Quadratic decay past optimal
    overshoot = (n - optimal_count) / optimal_count
    return max(0.0, 1.0 / (1.0 + overshoot ** 2))


def score_error_recovery(trace: Sequence[TraceEvent], faults_injected: int, faults_recovered: int) -> float:
    """Fraction of injected faults the agent recovered from. 1.0 if no faults injected."""
    if faults_injected == 0:
        return 1.0
    return max(0.0, min(1.0, faults_recovered / faults_injected))


def score_verification(trace: Sequence[TraceEvent]) -> float:
    """Reward verification events before 'final'. Penalize claiming done with no checks."""
    final_idx = next((i for i, e in enumerate(trace) if e.kind == "final"), len(trace))
    pre_final = trace[:final_idx]
    verifies = [e for e in pre_final if e.kind == "verify"]
    if not verifies:
        return 0.0
    # Saturating curve: 1 verify = 0.5, 2 = 0.75, 3+ = ~1.0
    return 1.0 - (0.5 ** len(verifies))


def score_artifact_quality(passes: int, total: int) -> float:
    """Pass-rate on the task's grader checks."""
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, passes / total))


def score_autonomy(trace: Sequence[TraceEvent]) -> float:
    """1 - (human_help / total_steps). Zero help = 1.0."""
    total = max(1, len(trace))
    help_calls = sum(1 for e in trace if e.kind == "human_help")
    return max(0.0, 1.0 - (help_calls / total))


def compute_scores(trace: Sequence[TraceEvent], result: TaskResult) -> DimensionScores:
    return DimensionScores(
        GD=score_goal_decomposition(trace, result.optimal_plan_steps),
        TS=score_tool_selection(trace, result.optimal_tool_count),
        ER=score_error_recovery(trace, result.injected_faults, result.faults_recovered),
        VD=score_verification(trace),
        AQ=score_artifact_quality(result.artifact_passes, result.artifact_total),
        AI=score_autonomy(trace),
    )


def aggregate(per_task: dict[str, DimensionScores]) -> dict[str, Any]:
    """Aggregate per-task scores into suite-level report."""
    if not per_task:
        return {"error": "no tasks scored"}
    keys = ["GD", "TS", "ER", "VD", "AQ", "AI"]
    means = {k: sum(getattr(s, k) for s in per_task.values()) / len(per_task) for k in keys}
    autoscores = [s.autoscore() for s in per_task.values()]
    suite_auto = math.exp(sum(math.log(max(a, 1e-3)) for a in autoscores) / len(autoscores))
    dummy = DimensionScores(**means)
    return {
        "n_tasks": len(per_task),
        "dimension_means": means,
        "suite_autoscore": suite_auto,
        "suite_tier": _tier_for(suite_auto),
        "per_task": {k: {**asdict(v), "autoscore": v.autoscore(), "tier": v.tier()} for k, v in per_task.items()},
    }


def _tier_for(s: float) -> str:
    if s < 0.30: return "T0-Demo"
    if s < 0.50: return "T1-Assistant"
    if s < 0.70: return "T2-Operator"
    if s < 0.85: return "T3-Engineer"
    if s < 0.95: return "T4-Senior"
    return "T5-Autonomous"


if __name__ == "__main__":
    # Self-test
    trace = [
        TraceEvent("plan", payload={"steps": ["a", "b", "c"]}),
        TraceEvent("tool_call", "read_file"),
        TraceEvent("tool_result", success=True),
        TraceEvent("tool_call", "run_cmd"),
        TraceEvent("tool_result", success=False),
        TraceEvent("tool_call", "run_cmd"),
        TraceEvent("tool_result", success=True),
        TraceEvent("verify", "pytest"),
        TraceEvent("final"),
    ]
    result = TaskResult(
        artifact_passes=4, artifact_total=5,
        optimal_tool_count=3, optimal_plan_steps=3,
        injected_faults=1, faults_recovered=1,
    )
    scores = compute_scores(trace, result)
    print(f"GD={scores.GD:.2f} TS={scores.TS:.2f} ER={scores.ER:.2f} "
          f"VD={scores.VD:.2f} AQ={scores.AQ:.2f} AI={scores.AI:.2f}")
    print(f"AutoScore={scores.autoscore():.3f} | Tier={scores.tier()}")
