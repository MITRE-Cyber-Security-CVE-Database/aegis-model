#!/usr/bin/env python3
"""
AutoBench orchestrator.
  python run.py --list
  python run.py --task code-synth/001-cidr-parser
  python run.py --category code-synth
  python run.py --all --report results.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).parent
TASKS_ROOT = ROOT / "tasks"

# Local imports work whether run as module or script
sys.path.insert(0, str(ROOT))
from scorer import (  # noqa: E402
    TraceEvent, TaskResult, compute_scores, aggregate,
)


def load_yaml(path: Path) -> dict:
    """Minimal YAML loader: prefers PyYAML, falls back to JSON."""
    text = path.read_text()
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        # Try JSON if yaml not available
        return json.loads(text)


def discover_tasks(category: str | None = None) -> list[Path]:
    tasks = []
    for cat_dir in sorted(TASKS_ROOT.iterdir()) if TASKS_ROOT.exists() else []:
        if not cat_dir.is_dir():
            continue
        if category and cat_dir.name != category:
            continue
        for task_dir in sorted(cat_dir.iterdir()):
            if (task_dir / "task.yaml").exists() or (task_dir / "task.json").exists():
                tasks.append(task_dir)
    return tasks


def load_task(task_dir: Path) -> dict:
    for fname in ("task.yaml", "task.json"):
        p = task_dir / fname
        if p.exists():
            return load_yaml(p)
    raise FileNotFoundError(f"No task spec in {task_dir}")


def load_grader(task_dir: Path):
    """Load the task-specific scorer.py (must export `grade(work_dir, trace) -> TaskResult`)."""
    spec_path = task_dir / "scorer.py"
    if not spec_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"grader_{task_dir.name}", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "grade", None)


def load_agent(name: str, model: str | None = None):
    if name == "ollama":
        from adapters.ollama_agent import OllamaAgent
        return OllamaAgent(model=model or "aegis:latest")
    if name == "noop":
        return _NoopAgent()
    raise ValueError(f"unknown agent: {name}")


def seed_fixtures(task_dir: Path, work_dir: Path):
    """Copy any files from <task>/fixtures/ into the agent's work_dir."""
    fx = task_dir / "fixtures"
    if not fx.exists():
        return
    import shutil
    for item in fx.iterdir():
        dst = work_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst)


class _NoopAgent:
    """Sanity-check agent: emits a plan + final, nothing else. Always scores ~0."""
    name = "noop"

    def run_task(self, task_spec, work_dir):
        from adapters.base import AgentResponse
        trace = [
            {"kind": "plan", "payload": {"steps": ["do nothing"]}},
            {"kind": "final", "payload": {"message": "noop"}},
        ]
        return AgentResponse(trace=trace, final_message="noop", tokens_used=0, wall_time_s=0.0)


def run_one(task_dir: Path, agent) -> dict:
    spec = load_task(task_dir)
    grader = load_grader(task_dir)
    work_dir = Path("/tmp") / f"autobench-work-{task_dir.name}-{int(time.time())}"
    work_dir.mkdir(parents=True, exist_ok=True)

    seed_fixtures(task_dir, work_dir)

    t0 = time.time()
    response = agent.run_task(spec, str(work_dir))
    elapsed = time.time() - t0

    # Convert trace dicts to TraceEvent
    trace_events = []
    for ev in response.trace:
        if isinstance(ev, dict):
            trace_events.append(TraceEvent(
                kind=ev.get("kind", ""),
                name=ev.get("name", ""),
                payload=ev.get("payload", {}),
                success=ev.get("success", True),
            ))
        else:
            trace_events.append(ev)

    # Grade
    if grader:
        result = grader(str(work_dir), trace_events, spec)
    else:
        # No grader → assume zero artifact passes
        result = TaskResult(
            artifact_passes=0,
            artifact_total=1,
            optimal_tool_count=spec.get("optimal_tool_count", 5),
            optimal_plan_steps=spec.get("optimal_plan_steps", 3),
        )

    scores = compute_scores(trace_events, result)
    return {
        "task": f"{task_dir.parent.name}/{task_dir.name}",
        "agent": agent.name,
        "elapsed_s": elapsed,
        "wall_time_s": response.wall_time_s,
        "tokens_used": response.tokens_used,
        "scores": asdict(scores),
        "autoscore": scores.autoscore(),
        "tier": scores.tier(),
        "trace_len": len(trace_events),
        "final": response.final_message,
    }


def main():
    p = argparse.ArgumentParser(description="AutoBench: autonomous agent benchmark")
    p.add_argument("--list", action="store_true", help="list discovered tasks")
    p.add_argument("--task", help="run a single task (category/name)")
    p.add_argument("--category", help="run all tasks in a category")
    p.add_argument("--all", action="store_true", help="run all tasks")
    p.add_argument("--agent", default="noop", help="agent adapter (ollama, noop)")
    p.add_argument("--model", help="model name (for ollama adapter)")
    p.add_argument("--report", help="write JSON report to path")
    args = p.parse_args()

    if args.list:
        tasks = discover_tasks()
        if not tasks:
            print(f"No tasks found under {TASKS_ROOT}")
            return
        for t in tasks:
            print(f"  {t.parent.name}/{t.name}")
        return

    if args.task:
        cat, name = args.task.split("/", 1)
        candidates = [t for t in discover_tasks(cat) if t.name == name]
        if not candidates:
            print(f"task not found: {args.task}")
            sys.exit(1)
        tasks = candidates
    elif args.category:
        tasks = discover_tasks(args.category)
    elif args.all:
        tasks = discover_tasks()
    else:
        p.print_help()
        return

    if not tasks:
        print("No matching tasks.")
        return

    agent = load_agent(args.agent, model=args.model)
    results = []
    score_map = {}
    for t in tasks:
        print(f"\n[AutoBench] Running {t.parent.name}/{t.name} with agent={agent.name}")
        try:
            r = run_one(t, agent)
            results.append(r)
            from scorer import DimensionScores
            score_map[r["task"]] = DimensionScores(**r["scores"])
            print(f"  -> AutoScore={r['autoscore']:.3f} [{r['tier']}]")
        except Exception as e:
            print(f"  -> ERROR: {e}")
            results.append({"task": f"{t.parent.name}/{t.name}", "error": str(e)})

    summary = aggregate(score_map) if score_map else {"error": "no scored tasks"}
    report = {"results": results, "summary": summary}

    print("\n=== AutoBench Summary ===")
    if "suite_autoscore" in summary:
        print(f"Tasks scored: {summary['n_tasks']}")
        print(f"Suite AutoScore: {summary['suite_autoscore']:.3f}")
        print(f"Suite Tier: {summary['suite_tier']}")
        print(f"Dimension means: " + ", ".join(f"{k}={v:.2f}" for k, v in summary["dimension_means"].items()))

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2))
        print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
