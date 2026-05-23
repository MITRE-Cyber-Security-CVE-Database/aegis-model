"""
Ollama agent adapter — runs the AEGIS GGUF model (or any local Ollama model)
against an AutoBench task using a minimal ReAct loop.

Tools available to the agent in the sandbox:
  - shell(cmd: str)      : run a shell command in /work
  - write_file(p, body)  : write a file
  - read_file(p)         : read a file
  - verify(check: str)   : run a verification command (e.g. pytest)
  - final(msg)           : declare task complete
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

from .base import AgentAdapter, AgentResponse


SYSTEM_PROMPT = """You are an autonomous engineering agent. Complete the task using ONLY the available tools.

Tools (call ONE per turn, formatted as JSON):
  {"tool": "shell",      "args": {"cmd": "<command>"}}
  {"tool": "write_file", "args": {"path": "<path>", "content": "<content>"}}
  {"tool": "read_file",  "args": {"path": "<path>"}}
  {"tool": "verify",     "args": {"cmd": "<command that exits 0 on success>"}}
  {"tool": "plan",       "args": {"steps": ["step1", "step2", ...]}}
  {"tool": "final",      "args": {"message": "<summary>"}}

RULES:
  1. Output exactly ONE JSON object per turn. Nothing else.
  2. Begin by emitting a plan.
  3. Verify your work with at least one verify call before final.
  4. You CANNOT ask the human for help. There is no human.
"""

TOOL_RE = re.compile(r"\{[^{}]*\"tool\"[^{}]*\}", re.DOTALL)


class OllamaAgent(AgentAdapter):
    name = "ollama"

    def __init__(self, model: str = "aegis:latest", host: str = "http://localhost:11434", max_steps: int = 20):
        self.model = model
        self.host = host
        self.max_steps = max_steps

    def _chat(self, messages: list[dict]) -> str:
        import urllib.request
        body = json.dumps({"model": self.model, "messages": messages, "stream": False}).encode()
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        return data.get("message", {}).get("content", "")

    def run_task(self, task_spec: dict, work_dir: str) -> AgentResponse:
        os.makedirs(work_dir, exist_ok=True)
        trace = []
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(task_spec)},
        ]
        t0 = time.time()
        tokens = 0
        final_msg = ""

        for step in range(self.max_steps):
            try:
                reply = self._chat(messages)
            except Exception as e:
                trace.append({"kind": "tool_result", "name": "_chat", "payload": {"error": str(e)}, "success": False})
                break

            tokens += len(reply.split())  # rough estimate

            match = TOOL_RE.search(reply)
            if not match:
                trace.append({"kind": "tool_result", "name": "_parse", "payload": {"raw": reply[:200]}, "success": False})
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "user", "content": "ERROR: emit a single JSON tool call."})
                continue

            try:
                call = json.loads(match.group(0))
            except json.JSONDecodeError as e:
                trace.append({"kind": "tool_result", "name": "_parse", "payload": {"error": str(e)}, "success": False})
                messages.append({"role": "user", "content": "ERROR: malformed JSON. Try again."})
                continue

            tool = call.get("tool", "")
            args = call.get("args", {}) or {}
            trace.append({"kind": "tool_call", "name": tool, "payload": args})
            messages.append({"role": "assistant", "content": match.group(0)})

            if tool == "plan":
                trace.append({"kind": "plan", "payload": {"steps": args.get("steps", [])}})
                obs = "Plan acknowledged. Proceed."
            elif tool == "shell":
                obs = self._shell(args.get("cmd", ""), work_dir, trace)
            elif tool == "write_file":
                obs = self._write(args.get("path", ""), args.get("content", ""), work_dir, trace)
            elif tool == "read_file":
                obs = self._read(args.get("path", ""), work_dir, trace)
            elif tool == "verify":
                obs = self._verify(args.get("cmd", ""), work_dir, trace)
            elif tool == "final":
                final_msg = args.get("message", "")
                trace.append({"kind": "final", "payload": {"message": final_msg}})
                break
            else:
                obs = f"unknown tool: {tool}"
                trace.append({"kind": "tool_result", "name": tool, "payload": {"error": obs}, "success": False})

            messages.append({"role": "user", "content": f"OBS: {obs[:1000]}"})

        return AgentResponse(trace=trace, final_message=final_msg, tokens_used=tokens, wall_time_s=time.time() - t0)

    # ---- tool implementations ----
    def _shell(self, cmd: str, cwd: str, trace: list) -> str:
        try:
            r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=60)
            ok = r.returncode == 0
            trace.append({"kind": "tool_result", "name": "shell", "payload": {"rc": r.returncode}, "success": ok})
            return (r.stdout + r.stderr)[:2000]
        except Exception as e:
            trace.append({"kind": "tool_result", "name": "shell", "payload": {"error": str(e)}, "success": False})
            return f"ERR: {e}"

    def _write(self, path: str, content: str, cwd: str, trace: list) -> str:
        try:
            target = Path(cwd) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            trace.append({"kind": "tool_result", "name": "write_file", "payload": {"path": path}, "success": True})
            return f"wrote {len(content)} bytes to {path}"
        except Exception as e:
            trace.append({"kind": "tool_result", "name": "write_file", "payload": {"error": str(e)}, "success": False})
            return f"ERR: {e}"

    def _read(self, path: str, cwd: str, trace: list) -> str:
        try:
            target = Path(cwd) / path
            content = target.read_text()[:2000]
            trace.append({"kind": "tool_result", "name": "read_file", "payload": {"path": path}, "success": True})
            return content
        except Exception as e:
            trace.append({"kind": "tool_result", "name": "read_file", "payload": {"error": str(e)}, "success": False})
            return f"ERR: {e}"

    def _verify(self, cmd: str, cwd: str, trace: list) -> str:
        try:
            r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
            ok = r.returncode == 0
            trace.append({"kind": "verify", "name": cmd, "payload": {"rc": r.returncode}, "success": ok})
            return f"verify rc={r.returncode}\n" + (r.stdout + r.stderr)[:1500]
        except Exception as e:
            trace.append({"kind": "verify", "name": cmd, "payload": {"error": str(e)}, "success": False})
            return f"ERR: {e}"
