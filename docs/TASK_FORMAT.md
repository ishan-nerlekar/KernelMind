# Task format

```
tasks/<id>/
  task.toml               metadata (below)
  instruction.md          the only text the agent sees: a symptom, never the fix
  environment/
    Dockerfile            must start with `ARG BASE_IMAGE=...` / `FROM ${BASE_IMAGE}`
    app/                  the buggy codebase; copied to /app and committed as one baseline commit
  tests/
    test.sh               writes 1 or 0 to $LOGS_DIR/reward.txt; details to $LOGS_DIR/results.json
  solution/solve.sh       reference fix: must pass
  alternatives/<n>/solve.sh   other valid fixes: must pass
  controls/<n>/solve.sh   plausible wrong fixes: must fail
  controls/<n>/expect.txt check names that must appear in failed_checks (one per line)
```

## task.toml

```toml
id = "dhcp-lease-writer"          # must match the directory name
tier = 1                          # 1 localized, 2 diagnose, 3 investigate
root_cause = "stale-state-on-update"
origin = "incident-derived"         # or "original" or "upstream"
language = "python"
summary = "one line"
starter_fails_on = ["mode"]       # the starter must fail on these checks

[limits]                          # optional; defaults shown
agent_timeout_sec = 1800
test_timeout_sec = 600
command_timeout_sec = 120

[docker]                          # optional
cap_add = []                      # e.g. ["NET_ADMIN"] for tasks using network namespaces
memory = "4g"
cpus = "2"
```

## Rules

- Scripts use `${APP_DIR:-/app}`, `${TESTS_DIR:-/tests}`, `${LOGS_DIR:-/logs/verifier}` and
  `$(dirname "$0")`, never hardcoded paths, so they run under both backends.
- `results.json` has `checks_total`, `checks_passed` and `failed_checks` (a list of check names).
  Check names describe behavior (`preservation`, `stale_state`), not test numbers.
- Builds happen in the Dockerfile or in `test.sh`; nothing in the task may need network at test time.
- No leaks: no git history, no comments or names pointing at the bug, no helper that already
  implements the fix, no test files in `app/`.
- Every control has a one-line comment in `expect.txt` saying what mistake it represents.
