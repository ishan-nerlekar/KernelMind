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
