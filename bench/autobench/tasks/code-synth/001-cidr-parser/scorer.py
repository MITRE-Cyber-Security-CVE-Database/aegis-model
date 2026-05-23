"""Grader for code-synth/001-cidr-parser."""
import os
import subprocess
import sys
from pathlib import Path

# Allow import of bench/autobench/scorer.py
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scorer import TaskResult  # type: ignore


CHECKS = [
    ("cidr_exists", lambda w: (Path(w) / "cidr.py").exists()),
    ("test_exists", lambda w: (Path(w) / "test_cidr.py").exists()),
    ("pytest_passes", lambda w: subprocess.run(
        ["python", "-m", "pytest", "test_cidr.py", "-q"],
        cwd=w, capture_output=True, timeout=30
    ).returncode == 0),
    ("six_hosts_in_29", lambda w: subprocess.run(
        ["sh", "-c", "python cidr.py 10.0.0.0/29 | wc -l"],
        cwd=w, capture_output=True, timeout=10, text=True
    ).stdout.strip() == "6"),
    ("invalid_exits_nonzero", lambda w: subprocess.run(
        ["python", "cidr.py", "not-a-cidr"],
        cwd=w, capture_output=True, timeout=10
    ).returncode != 0),
]


def grade(work_dir: str, trace, task_spec: dict) -> TaskResult:
    passes = 0
    for name, check in CHECKS:
        try:
            if check(work_dir):
                passes += 1
        except Exception:
            pass
    return TaskResult(
        artifact_passes=passes,
        artifact_total=len(CHECKS),
        optimal_tool_count=task_spec.get("optimal_tool_count", 4),
        optimal_plan_steps=task_spec.get("optimal_plan_steps", 4),
    )
