# Verifier audit

Plan: `tasks/plan.md`. This file records how the audit is run and what it finds.

## Terminal-Bench 2.0 setup

- Source: https://github.com/harbor-framework/terminal-bench-2 (Apache-2.0), pinned at
  `2fd12b88aafdd04a52c298e3940bcb189f9766d6` (2026-04-29), cloned to `external/tb2/` (gitignored).
- 89 tasks in Harbor format: `task.toml`, `instruction.md`, `environment/Dockerfile`, `tests/test.sh`
  (writes `/logs/verifier/reward.txt` and pytest results to `ctrf.json`), `solution/solve.sh`.
- KernelMind loads them with `--tasks-dir`. Harbor `task.toml` fields map onto KernelMind's (memory,
  CPUs, timeouts); `allow_internet = true` turns on container networking. **All 89 tasks need it:**
  each `test.sh` installs curl and uv at grading time.
- Failed test names come from `ctrf.json` when the task doesn't write KernelMind's `results.json`.

## T1 spike (Nov 6)

```sh
kernelmind validate --tasks-dir external/tb2 cancel-async-tasks regex-log sqlite-db-truncate
```

Expected: for each task, the starter (no solution) fails and the reference `solve.sh` passes.
Record build time, test time, and any task that doesn't build or run on Apple Silicon.

**Result (Nov 6):** all three valid under Docker on the Mac (starter fails, reference passes).

## T2/T3: candidates and the pilot

`kernelmind audit` (in `kernelmind/audit.py`) copies each task, adds candidates, and grades them with
`validate`:

| Candidate | Made by | Should | If it doesn't |
|---|---|---|---|
| Mutant: one changed number, comparison or boolean in the reference solution, or one deleted shell step | Code, deterministic per task | Fail | Lenient suspect, unless the mutant is equivalent (still correct) |
| Near miss: breaks exactly one sentence of the instruction (categories: partial, edge-case, symptom, over-broad, hardcoded, format) | A cheap model, shown the instruction and reference solution but never the tests | Fail | Lenient suspect |
| Alternative: meets every requirement in a different way | Same model | Pass | Strict suspect |

A candidate whose own script crashes is `broken-candidate` and says nothing about the grader.
Suspects are only findings after confirmation (T6). Mutant comparisons skip shell redirects; mutants
are spread across lines; dependency pins and URLs are never mutated.

Pilot command:

```sh
kernelmind audit --tasks-dir external/tb2 --out results/audit-pilot --model claude-haiku-5-5 --max-cost 1 \
  cancel-async-tasks regex-log sqlite-db-truncate log-summary-date-ranges large-scale-text-editing
```

First pilot attempt (Nov 6) crashed before grading anything: the model rejected `temperature=0.7`.
Fixed in the next commit (default temperature; a failed generation no longer stops the run).
