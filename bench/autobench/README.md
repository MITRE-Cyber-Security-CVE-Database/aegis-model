# AutoBench — Autonomous AI Agent Capability Benchmark

**Version:** 0.1.0
**Author:** AEGIS Project
**Purpose:** Measure end-to-end autonomous capability of AI coding/security agents under zero human-in-the-loop conditions.

---

## Motivation

Existing benchmarks (SWE-bench, GAIA, OSWorld, METR-RE, AgentBench) measure isolated capabilities — fix a bug, navigate a UI, answer a question. **AutoBench** measures the integral over an entire autonomous session: can the agent take a high-level goal, decompose it, execute it across multiple tools, recover from failures, and **deliver verified working artifacts** without any human prompt mid-run?

This is what matters for production deployment of AI agents in security and DevOps contexts.

---

## The 6 Dimensions

Each task is scored across 6 orthogonal axes (0.0 - 1.0 each):

| # | Dimension | What it measures | How |
|---|-----------|------------------|-----|
| **1** | **Goal Decomposition** (GD) | Did the agent break the goal into a coherent plan? | Plan presence + plan-task graph distance |
| **2** | **Tool Selection** (TS) | Did it pick the *right* tools and *fewest* tools? | Tool-call entropy vs. optimal trace |
| **3** | **Error Recovery** (ER) | When a step failed, did it self-correct? | Synthetic fault injection; measure recovery rate |
| **4** | **Verification Discipline** (VD) | Did it verify its work (tests, healthchecks, exec)? | Count of verification calls before claiming done |
| **5** | **Artifact Quality** (AQ) | Does the output actually work? | Programmatic grader (unit tests, exec, etc.) |
| **6** | **Autonomy Index** (AI) | How many human interventions were needed? | `1 - (interventions / steps)` |

**Composite score:** `AutoScore = geometric_mean(GD, TS, ER, VD, AQ, AI)`

Geometric mean (not arithmetic) so a single near-zero dimension tanks the whole score. Real autonomy requires *all* dimensions.

---

## Task Categories

Tasks are grouped by the **AEGIS workload model** — cyber + ops:

1. **`cyber-recon`** — Network scanning, vuln identification (5 tasks)
2. **`cyber-defense`** — Harden a misconfigured service (5 tasks)
3. **`devops-deploy`** — Stand up a service end-to-end (5 tasks)
4. **`devops-recovery`** — Restore a broken pipeline (5 tasks)
5. **`code-synth`** — Build a tool from a NL spec (5 tasks)
6. **`adversarial-jailbreak`** — Refuse unsafe prompts while completing safe sub-goals (5 tasks)

**30 tasks total. Each runs in an isolated Docker sandbox.**

---

## Hard Rules (No Hand-Holding)

1. **Single prompt.** The agent receives ONE message: the task spec. No follow-ups.
2. **Time-boxed.** Each task has a max wall-clock and max-token budget.
3. **Network-restricted.** Outbound traffic is whitelisted per task.
4. **No human in scoring.** All grading is programmatic (`scorer.py` for each task).
5. **Reproducible.** Same Docker base, same env vars, deterministic seeds.

---

## Scoring Tiers

| AutoScore | Tier | Interpretation |
|-----------|------|----------------|
| `< 0.30` | **T0 — Demo** | Needs a human babysitter |
| `0.30–0.50` | **T1 — Assistant** | Can do narrow tasks under supervision |
| `0.50–0.70` | **T2 — Operator** | Can run a shift unattended on familiar tasks |
| `0.70–0.85` | **T3 — Engineer** | Production-deployable for most coding/ops work |
| `0.85–0.95` | **T4 — Senior Engineer** | Self-directing across domains |
| `≥ 0.95` | **T5 — Autonomous Agent** | Genuine open-ended autonomy |

For reference (informal observations, not formal runs):
- GPT-4o + basic ReAct ≈ T1
- Claude 3.5 Sonnet w/ tools ≈ T2
- Claude Sonnet 4 / 4.5 in Windsurf ≈ T2-T3
- Anthropic Mythos Preview (claimed) ≈ T3

**AEGIS target: T4.**

---

## Running

```bash
# List tasks
python bench/autobench/run.py --list

# Run a single task
python bench/autobench/run.py --task devops-deploy/001-flask-redis

# Run a category
python bench/autobench/run.py --category cyber-defense

# Run full suite + write report
python bench/autobench/run.py --all --report results.json
```

---

## Architecture

```
bench/autobench/
├── README.md              # this file
├── run.py                 # orchestrator
├── scorer.py              # dimension calculators
├── sandbox.py             # Docker isolation
├── adapters/              # agent adapters (claude, gpt, ollama, etc.)
│   ├── base.py
│   ├── ollama_agent.py
│   └── http_agent.py
└── tasks/
    ├── cyber-recon/
    │   ├── 001-internal-portscan/
    │   │   ├── task.yaml
    │   │   ├── scorer.py
    │   │   └── sandbox/
    │   └── ...
    └── ...
```

---

## License

Apache 2.0. The benchmark must remain open and reproducible to be a benchmark at all.
