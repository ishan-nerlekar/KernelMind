# KernelMind

A benchmark of **systems debugging** tasks for coding agents. Each task drops an agent into a
sandboxed codebase with a symptom (a bug report, logs, a failing command) and checks, with hidden
tests, whether it found and fixed the root cause without breaking anything else.

Tasks come from two sources: patterns from real production networking incidents (rewritten as
original code, no proprietary material) and original bugs planted in purpose-built network systems.

> **Status (Nov 5, 2026):** harness and [spec](docs/SPEC.md) complete; 2 Tier 1 tasks ported from v1.
> Tier 2/3 tasks and the first multi-model results are in progress. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Results

No model results yet. The first checkpoint run is scheduled for Nov 12.

## Quickstart

```sh
pip install -e ".[agents]"
kernelmind list
kernelmind validate                         # every task: starter fails, fixes pass, wrong fixes fail
kernelmind run --agent oracle               # pipeline check: must score 100%
export ANTHROPIC_API_KEY=...                # or OPENAI_API_KEY, etc.
kernelmind run --agent mini --model claude-opus-5-5 --attempts 3 --max-cost 20   # see docs/MODELS.md
kernelmind report results/<run-id>
```

Requires Python 3.11+ and Docker. `--backend local` runs validation without Docker for task
development only; agents always run in Docker.

## How a task is graded

1. Fresh container from the task's Dockerfile: no network, capped memory/CPU/processes.
2. The agent (mini-swe-agent; same prompt, tools and budget for every model) works in `/app`.
3. Hidden tests are copied in only after the agent stops, then run.
4. Pass = all hidden checks pass. Scores: pass@1 with bootstrap 95% CI, pass@k, per tier.

## Task tiers

| Tier | Agent gets | Must do |
|---|---|---|
| 1 Localized | Small codebase plus an explicit contract | Fix one function |
| 2 Diagnose | Real codebase, bug report, logs | Find the faulty component, fix without regressions |
| 3 Investigate | Running multi-process system | Reproduce, observe, isolate, fix |

## Task validation

A task is admitted only if `kernelmind validate` shows the starter failing on the intended check,
the reference and alternative fixes passing, and at least three plausible wrong fixes failing on
the checks that target their mistakes. See [docs/TASK_FORMAT.md](docs/TASK_FORMAT.md).

## Repository

```
kernelmind/   harness: tasks, sandbox, validation, agents, scoring
tasks/        one directory per task
docs/         spec, task format, models, roadmap, changelog
learning/     lessons written alongside the build
results/      run outputs (not committed except published runs)
```
