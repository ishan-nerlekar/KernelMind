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

## Pilot results (Nov 6): 5 tasks, $0.02 of generation

| Task | Baseline | Mutants caught | Near misses caught | Alternatives accepted | Confirmed findings |
|---|---|---|---|---|---|
| cancel-async-tasks | ok | – (none generated) | 4/4 | 2/2 | – |
| large-scale-text-editing | ok | 6/6 | 4/4 | 2/2 | – |
| log-summary-date-ranges | image build failed (transient) | – | – | – | rerun |
| regex-log | ok | 3/6 | 3/4 | 1/1 (1 broken) | **4 lenient** |
| sqlite-db-truncate | ok | 2/5 (1 broken) | 3/4 | 1/2 | – |

(The summary table the run printed undercounted model-written candidates because of a bug, now fixed.
These counts come from the per-task JSON.)

### regex-log: 4 confirmed lenient findings

The verifier accepts four regexes that are wrong by the instruction's own words. Each was confirmed by
a differential probe: one log line where the reference regex is right and the candidate is wrong.

| Candidate | Change | Probe line | Instruction says | Candidate returns |
|---|---|---|---|---|
| near-1 (model-written, "partial") | February limited to 28 days | `Login from 10.0.0.1 on 2021-02-29` | match: "February can have up to 29 days in all years" | no match |
| mut-3 | 30-day months accept day 31 | `Login from 10.0.0.1 on 2020-04-31` | no match (not a date) | `2020-04-31` |
| mut-2 | month `05` replaced by `6` | `Login from 10.0.0.1 on 2020-05-20` | match | no match |
| mut-5 | last IPv4 octet rejects 250 | `Login from 10.0.0.250 on 2020-01-01` | match | no match |

Root causes in `tests/test_outputs.py`:
- **Confounded negative samples.** The two samples commented "invalid date 30th February" and
  "invalid date 31th April" also contain the invalid IP `172.16.0.256`, so they are rejected for the
  IP. With a valid date they are still rejected, so they never test the date rule.
- **No positive sample for February 29**, though the instruction states it explicitly.
- **Months 04–11 never appear in a matching line** except via the confounded samples; octets 250–254
  never appear in the last position.

### sqlite-db-truncate: no findings
- The 3 surviving mutants are equivalent (byte-search start offset, step size, JSON indent): run on
  the task's real `trunc.db`, each recovers the same 8 rows as the reference.
- The surviving near miss (stops at the first undecodable row) also recovers all 8 rows on this
  database, so it is not wrong on the graded input.
- The strict suspect (`alt-1`) called the `sqlite3` CLI, which the image doesn't have; the script
  kept going and wrote an empty file. A broken candidate, not a strict grader.
- Observation, not counted: the test passes with 7 of the 8 rows and ignores invented rows, while the
  instruction says "recover as many of the rows as possible". Possibly a deliberate tolerance.

### Harness fixes from the pilot
- Candidate metadata overwrote `kind`, so the summary miscounted. Fixed, with a unit test.
- Model-written candidates now run with `set -e`, so a failing step makes them broken instead of
  producing misleading output (the `alt-1` case).
- Image builds retry once; tasks whose baseline broke are re-audited on resume; model calls time out
  after 240 s with 2 retries (one call hung for 600 s).

## T5 task selection (fixed Nov 6, before any T5 results)

Eligible: no GPU; category not model-training, machine-learning or video-processing; Dockerfile with
at most 4 RUN/COPY steps; reference `solve.sh` at most 250 lines; at most 8 GB of memory; agent
timeout at most 1,200 s; the reference solution downloads models or builds large projects at most
once (regex `huggingface|from_pretrained|wget|git clone|make -j|opam|cargo build`); not in the pilot.
33 tasks are eligible; 25 were sampled with `random.Random(20261106)`. The heaviness rules were
added after a first draw included CompCert and model downloads, before anything was run.

break-filter-js-from-html build-pmars cobol-modernization code-from-image configure-git-webserver
constraints-scheduling db-wal-recovery fix-git git-leak-recovery git-multibranch headless-terminal
merge-diff-arc-agi-task modernize-scientific-stack openssl-selfsigned-cert overfull-hbox
password-recovery polyglot-c-py polyglot-rust-c prove-plus-comm raman-fitting sanitize-git-repo
sparql-university torch-pipeline-parallelism torch-tensor-parallelism tune-mjcf
