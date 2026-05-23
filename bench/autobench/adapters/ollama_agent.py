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
  3. After writing or changing ANY file, you MUST run verify (e.g. pytest, test script, or the task's success check).
  4. You are NOT allowed to call final until verify has returned exit code 0 (success). If verify fails, diagnose the error, fix it, and verify again.
  5. A verify result of "rc=0" means success. "rc=1" or any non-zero means failure — fix the underlying issue before proceeding.
  6. You CANNOT ask the human for help. There is no human.
"""

def _extract_json_object(text: str) -> str | None:
    """Find the first JSON object containing '"tool"' by bracket-balancing.

    The simple regex \\{[^{}]*"tool"[^{}]*\\} fails on nested objects/arrays
    (e.g. {"tool":"plan","args":{"steps":["a","b"]}}), so we walk the string
    counting braces while respecting string literals.
    """
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        j = i
        in_str = False
        esc = False
        while j < n:
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[i:j + 1]
                        if '"tool"' in candidate:
                            return candidate
                        break
            j += 1
        i += 1
    return None


class OllamaAgent(AgentAdapter):
    name = "ollama"

    def __init__(self, model: str = "aegis:latest", host: str = "http://localhost:11434",
                 max_steps: int = 12, max_bad_parses: int = 3):
        self.model = model
        self.host = host
        self.max_steps = max_steps
        self.max_bad_parses = max_bad_parses

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
        bad_parses = 0

        for step in range(self.max_steps):
            try:
                reply = self._chat(messages)
            except Exception as e:
                trace.append({"kind": "tool_result", "name": "_chat", "payload": {"error": str(e)}, "success": False})
                break

            tokens += len(reply.split())  # rough estimate

            extracted = _extract_json_object(reply)
            if extracted is None:
                bad_parses += 1
                trace.append({"kind": "tool_result", "name": "_parse", "payload": {"raw": reply[:200]}, "success": False})
                if bad_parses >= self.max_bad_parses:
                    trace.append({"kind": "final", "payload": {"message": "aborted: too many parse failures"}})
                    break
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "user", "content": "ERROR: emit a single JSON tool call containing a 'tool' key."})
                continue

            try:
                call = json.loads(extracted)
            except json.JSONDecodeError as e:
                bad_parses += 1
                trace.append({"kind": "tool_result", "name": "_parse", "payload": {"error": str(e)}, "success": False})
                if bad_parses >= self.max_bad_parses:
                    trace.append({"kind": "final", "payload": {"message": "aborted: too many parse failures"}})
                    break
                messages.append({"role": "user", "content": "ERROR: malformed JSON. Try again."})
                continue

            tool = call.get("tool", "")
            args = call.get("args", {}) or {}
            trace.append({"kind": "tool_call", "name": tool, "payload": args})
            messages.append({"role": "assistant", "content": extracted})

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
    # Hardened env passed to every subprocess: no interactive prompts, no sudo,
    # no Python path bleed-through. Prevents stuck `sudo` prompts blocking the run.
    _SAFE_ENV = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": "/tmp",
        "LANG": "C.UTF-8",
        "SUDO_ASKPASS": "/bin/false",
        "DEBIAN_FRONTEND": "noninteractive",
        "PYTHONUNBUFFERED": "1",
        # Block sudo entirely by intercepting it on PATH
        "SUDO": "/bin/false",
    }

    # Commands the agent is never allowed to run (sandboxed but defense-in-depth)
    _FORBIDDEN = ("sudo ", "su ", "doas ", "pkexec ", " sudo", ";sudo", "&&sudo")

    def _shell(self, cmd: str, cwd: str, trace: list) -> str:
        for token in self._FORBIDDEN:
            if token in f" {cmd} ":
                trace.append({"kind": "tool_result", "name": "shell",
                              "payload": {"blocked": True, "cmd": cmd[:200]}, "success": False})
                return "ERR: command blocked (privilege escalation not permitted in sandbox)"
        try:
            r = subprocess.run(
                cmd, shell=True, cwd=cwd,
                capture_output=True, text=True, timeout=60,
                stdin=subprocess.DEVNULL,
                env=self._SAFE_ENV,
            )
            ok = r.returncode == 0
            trace.append({"kind": "tool_result", "name": "shell", "payload": {"rc": r.returncode}, "success": ok})
            return (r.stdout + r.stderr)[:2000]
        except subprocess.TimeoutExpired:
            trace.append({"kind": "tool_result", "name": "shell", "payload": {"error": "timeout"}, "success": False})
            return "ERR: command timed out after 60s"
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
        for token in self._FORBIDDEN:
            if token in f" {cmd} ":
                trace.append({"kind": "verify", "name": cmd,
                              "payload": {"blocked": True}, "success": False})
                return "ERR: command blocked"
        try:
            r = subprocess.run(
                cmd, shell=True, cwd=cwd,
                capture_output=True, text=True, timeout=120,
                stdin=subprocess.DEVNULL,
                env=self._SAFE_ENV,
            )
            ok = r.returncode == 0
            trace.append({"kind": "verify", "name": cmd, "payload": {"rc": r.returncode}, "success": ok})
            return f"verify rc={r.returncode}\n" + (r.stdout + r.stderr)[:1500]
        except subprocess.TimeoutExpired:
            trace.append({"kind": "verify", "name": cmd, "payload": {"error": "timeout"}, "success": False})
            return "ERR: verify timed out after 120s"
        except Exception as e:
            trace.append({"kind": "verify", "name": cmd, "payload": {"error": str(e)}, "success": False})
            return f"ERR: {e}"
