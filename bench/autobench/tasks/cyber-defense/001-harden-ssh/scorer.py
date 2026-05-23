"""Grader for cyber-defense/001-harden-ssh."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scorer import TaskResult  # type: ignore


def _kv(text: str, key: str):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        m = re.match(rf"^{re.escape(key)}\s+(\S+)", line, re.IGNORECASE)
        if m:
            return m.group(1).lower()
    return None


CHECKS = [
    ("permit_root_no",   lambda t: _kv(t, "PermitRootLogin") == "no"),
    ("password_auth_no", lambda t: _kv(t, "PasswordAuthentication") == "no"),
    ("empty_pw_no",      lambda t: _kv(t, "PermitEmptyPasswords") == "no"),
    ("x11_forward_no",   lambda t: _kv(t, "X11Forwarding") == "no"),
    ("max_auth_tries",   lambda t: (_kv(t, "MaxAuthTries") or "99").isdigit() and int(_kv(t, "MaxAuthTries")) <= 3),
    ("no_protocol_1",    lambda t: (_kv(t, "Protocol") or "2") != "1"),
]


def grade(work_dir, trace, task_spec):
    out_path = Path(work_dir) / "sshd_config.output"
    passes = 0
    if out_path.exists():
        text = out_path.read_text()
        for name, check in CHECKS:
            try:
                if check(text):
                    passes += 1
            except Exception:
                pass
    return TaskResult(
        artifact_passes=passes,
        artifact_total=len(CHECKS),
        optimal_tool_count=task_spec.get("optimal_tool_count", 4),
        optimal_plan_steps=task_spec.get("optimal_plan_steps", 3),
    )
