#!/usr/bin/env python3
"""
AutoBench multi-model comparison.
Runs the benchmark against multiple Ollama models and produces a side-by-side table.

Usage:
  python compare.py qwen2.5-coder:3b qwen2.5-coder:7b-instruct hancock-auditor:latest
  python compare.py --report-dir results/

Outputs:
  - JSON per model in results/<model>.json
  - Markdown table to stdout
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"


def run_model(model: str, results_dir: Path) -> Path:
    safe = model.replace(":", "-").replace("/", "_")
    out = results_dir / f"{safe}.json"
    print(f"\n=== Running {model} → {out.name} ===", flush=True)
    subprocess.run([
        sys.executable, "-u", str(ROOT / "run.py"),
        "--all", "--agent", "ollama", "--model", model,
        "--report", str(out),
    ], check=False)
    return out


def load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def format_table(reports: dict[str, dict]) -> str:
    rows = []
    rows.append("| Model | AutoScore | Tier | GD | TS | ER | VD | AQ | AI |")
    rows.append("|-------|-----------|------|----|----|----|----|----|-----|")
    for model, report in reports.items():
        s = report.get("summary", {})
        if "suite_autoscore" not in s:
            rows.append(f"| `{model}` | — | error | — | — | — | — | — | — |")
            continue
        m = s["dimension_means"]
        rows.append(
            f"| `{model}` | **{s['suite_autoscore']:.3f}** | {s['suite_tier']} | "
            f"{m['GD']:.2f} | {m['TS']:.2f} | {m['ER']:.2f} | "
            f"{m['VD']:.2f} | {m['AQ']:.2f} | {m['AI']:.2f} |"
        )
    return "\n".join(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("models", nargs="*", help="Ollama models to benchmark")
    p.add_argument("--report-dir", default=str(RESULTS), help="Where to write JSON reports")
    p.add_argument("--summary-only", action="store_true",
                   help="Skip running; just summarize existing reports in --report-dir")
    args = p.parse_args()

    results_dir = Path(args.report_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    reports: dict[str, dict] = {}

    if args.summary_only:
        for f in sorted(results_dir.glob("*.json")):
            data = load(f)
            if data:
                reports[f.stem] = data
    else:
        if not args.models:
            print("ERR: pass at least one model name, or use --summary-only", file=sys.stderr)
            sys.exit(1)
        for m in args.models:
            out = run_model(m, results_dir)
            data = load(out)
            if data:
                reports[m] = data

    if not reports:
        print("No reports to summarize.")
        return

    print("\n## AutoBench Comparison\n")
    print(format_table(reports))
    print()

    # Pick best
    best = max(reports.items(), key=lambda kv: kv[1].get("summary", {}).get("suite_autoscore", 0))
    print(f"**Winner:** `{best[0]}` "
          f"(AutoScore = {best[1]['summary']['suite_autoscore']:.3f}, "
          f"{best[1]['summary']['suite_tier']})")


if __name__ == "__main__":
    main()
