"""
Docker sandbox: runs each AutoBench task in an isolated, network-restricted container.
"""
from __future__ import annotations

import os
import json
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    artifacts_dir: str  # host path with artifacts the agent produced


class DockerSandbox:
    """
    Spins up an isolated container per task.
    - Mounts task spec read-only
    - Mounts an empty 'work' dir read-write for agent output
    - Optional network whitelist via --add-host / no-network
    """

    def __init__(self, image: str = "python:3.11-slim", timeout: int = 600, allow_network: bool = False):
        self.image = image
        self.timeout = timeout
        self.allow_network = allow_network

    def run(self, task_dir: Path, command: list[str], extra_env: dict | None = None) -> SandboxResult:
        run_id = uuid.uuid4().hex[:8]
        host_work = Path(tempfile.mkdtemp(prefix=f"autobench-{run_id}-"))
        container_name = f"autobench-{run_id}"

        args = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--cpus", "2",
            "--memory", "2g",
            "--pids-limit", "256",
            "--read-only",
            "--tmpfs", "/tmp:rw,size=512m",
            "-v", f"{task_dir.absolute()}:/task:ro",
            "-v", f"{host_work}:/work:rw",
            "-w", "/work",
        ]
        if not self.allow_network:
            args += ["--network", "none"]
        for k, v in (extra_env or {}).items():
            args += ["-e", f"{k}={v}"]
        args.append(self.image)
        args += command

        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            return SandboxResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                artifacts_dir=str(host_work),
            )
        except subprocess.TimeoutExpired as e:
            # Best-effort kill
            subprocess.run(["docker", "kill", container_name], capture_output=True)
            return SandboxResult(
                exit_code=124,
                stdout=(e.stdout or "").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""),
                stderr=f"TIMEOUT after {self.timeout}s\n" + (
                    (e.stderr or "").decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
                ),
                artifacts_dir=str(host_work),
            )

    def cleanup(self, result: SandboxResult):
        shutil.rmtree(result.artifacts_dir, ignore_errors=True)


def docker_available() -> bool:
    try:
        r = subprocess.run(["docker", "version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False
