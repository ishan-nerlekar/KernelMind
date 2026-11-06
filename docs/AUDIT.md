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

## T5 early notes (run in progress)

- `build-pmars`: **Terminal-Bench's own reference solution fails.** `solve.sh` pins
  `dpkg-dev=1.22.21`, which the Debian archive no longer serves, so the oracle can't run today. A
  different finding class from leniency/strictness: environment drift breaks the task itself. Confirm
  on x86 / Harbor before reporting.
- `break-filter-js-from-html`: the reference runs but fails its own test, which drives headless
  Chromium through Selenium. Most likely our container (Apple Silicon, shared memory, process limits),
  so: baseline broken in our harness, excluded, not a finding.

## T4: auditor validated on planted flaws

`tools/plant_flaws.py` copies 12 fast KernelMind tasks (apnet) to `audit/planted-kernelmind/` and
disables (renames) the tests that catch the task's first wrong-fix control. That control is the
witness: it must now pass the weakened grader. Planting took three passes:
1. Disabling only the pinned check left 9 of 12 witnesses still caught: wrong fixes usually fail
   more checks than the one they're pinned to.
2. Disabling every check the witness failed made 11 of 12 pass.
3. `x-push-lost-update` (the concurrency task) was dropped: its witness passes on some runs and fails
   on others, so it has no stable ground truth.

Result: **11 planted flaws**. In 4 (`frame-partial-read`, `neigh-roam-flush`,
`radio-monitor-capability`, `rate-counter-wrap`) the weakened grader also passes the untouched
starter: gross flaws. The other 7 are subtle (the starter still fails).

`tools/audit_planted.py` audits each weakened copy, then regrades the **same** candidates against the
original tests:
- detected = some candidate (or the untouched starter) passes the weakened grader and fails the sound one;
- suspects against the sound grader = equivalent mutants, bad candidates, or real gaps in KernelMind's tests.

Dry run, mutants only (no model): gross 4/4 detected (via the starter), subtle 0/7. So subtle
detection has to come from the model-written near misses; the real run measures that.

The dry run also audited KernelMind's own graders (3 suspects against sound graders):
- `seq-wraparound` `int16(a-b) > 0` → `>= 0`: equivalent (with `a != b` the difference is never 0).
- `neigh-roam-flush` per-interface count not moved on roam: equivalent after the fix, because the
  per-interface counter no longer affects anything observable.
- `peer-timeout-flap` NotFound sets `Stale = true`: **a real gap in KernelMind's tests.** `Stale` is
  documented as "the last poll timed out", and no test checks it after a NotFound result.

Also from the dry run: `baseline_ok` now means "the reference passes". A grader that passes the
untouched starter is reported as its own finding, "doing nothing passes".

## T5 results (Nov 6–7): 26 tasks, $0.12 of generation

Graded 20 of 26 (6 broken baselines, below). With the pilot that makes **24 graded Terminal-Bench
2.0 tasks**. Candidate outcomes on the 20 graded T5 tasks:

| | Caught / accepted (as they should be) | Suspect | Broken candidate |
|---|---|---|---|
| Mutants (should fail) | 42 | 47 lenient | 19 |
| Model-written near misses (should fail) | 40 | 16 lenient | 8 |
| Model-written alternatives (should pass) | 19 | 7 strict | 6 |

Generation failed for 4 tasks (Haiku returned invalid JSON for `torch-pipeline-parallelism` and
`torch-tensor-parallelism`, nothing parsable for `constraints-scheduling` and `polyglot-rust-c`); only
their mutants were graded.

### Broken baselines (not grader findings)

| Task | Cause | Status |
|---|---|---|
| prove-plus-comm | our harness ran commands in `/app`; the image's `WORKDIR` is `/workspace` | **harness fixed**: external tasks now run in their image's WORKDIR |
| git-multibranch | reference `solve.sh` failed while creating users and setting up the git server; our sandbox set `no-new-privileges` | **harness fixed** for external tasks; rerun to confirm |
| fix-git | image build failed in the task's own `setup.sh` (error cut off) | undetermined; rerun |
| break-filter-js-from-html | the reference fails its own headless-Chromium test | probably our container on Apple Silicon; excluded |
| tune-mjcf | the reference fails `test_model_speed` | hardware-dependent timing test; excluded |
| build-pmars | the reference pins `dpkg-dev=1.22.21`, no longer served by Debian | **possible finding (environment drift)**; confirm on x86 under Harbor |

### Triage of the 23 model-written suspects (T6, first pass)

**Confirmed lenient: 10 suspects in 6 tasks.** Each candidate breaks a requirement stated in the
instruction, and the official tests pass it.

| Task | What the passing candidate does wrong | Why the tests miss it |
|---|---|---|
| git-leak-recovery (near-1, near-3) | leaves the secret recoverable: `git show bd81824` (a dangling commit) prints it | the "unreachable objects" check runs `cat-file -p` on dangling *commits*, which prints the commit header, not the blob holding the secret; reflog-reachable objects are never "dangling" |
| git-leak-recovery (near-4) | rewrites every commit message (`[sanitized] chore: init …`) although "commit messages remain untouched" | the test checks that one message *contains* `chore: init …` |
| configure-git-webserver (near-4) | the post-receive hook writes a literal `hello world` file, ignoring what was pushed | `verify.sh` pushes exactly the instruction's example, `hello world`, and checks for exactly that |
| db-wal-recovery (near-4) | writes the right JSON but never fixes the WAL ("1. Fix the WAL file so SQLite can read it") | only `recovered.json` is checked |
| modernize-scientific-stack (near-1) | `requirements.txt` with no version constraints ("Specify version constraints using >=, ==, or ~=") | only the file's existence is checked |
| modernize-scientific-stack (near-4) | edits the original script marked "DO NOT MODIFY" | the original is never checked |
| cobol-modernization (near-2) | the Python port skips the COBOL program's seller-owns-book check | all three graded transactions are valid sales, so the rejection path is never exercised |
| sparql-university (near-1) | counts `GB` as an EU member (the UK left in 2020; the reference date is 2025-08-16) | the graph has no `GB` literal at all |
| sparql-university (near-2) | `COUNT(...) >= 10` for "more than 10 students" | no department has exactly 10 |

With the pilot's `regex-log` (4 confirmed), **7 of 24 graded tasks (29%) have at least one confirmed
lenient verifier gap.**

Recurring causes:
1. **Requirements stated but never tested** (modernize ×2, db-wal, git-leak commit messages).
2. **One fixed input that lacks the distinguishing case** (cobol, sparql ×2, regex-log Feb 29).
3. **Test input identical to the instruction's example**, so hardcoding passes (configure-git-webserver).
4. **Confounded negative samples**: a sample meant to test rule A also breaks rule B (regex-log).
5. **The check inspects the wrong object** (git-leak: commit headers instead of their contents).

**Rejected: 6 near misses that weren't real violations.**
- password-recovery ×2: the instruction allows multiple guesses, and the tests check that the true
  password is among them.
- openssl-selfsigned-cert ×2: the "unconditional success" script actually loads the certificate; the
  other only crashes instead of reporting.
- sanitize-git-repo: the test compares lowercased text, so the claimed case-variant leftover would be
  caught (the candidate's premise was false).
- overfull-hbox: a fixed table of word swaps is a legitimate solution for this one document.

**Strict suspects (7): none confirmed.**
- sparql-university ×2: the alternatives return different (wrong) answers. Rejected.
- headless-terminal ×2: both fail the interactive, cancel and background tests. Either the
  alternatives are wrong or the tests are timing-sensitive. **Unresolved**: needs a run in the container.
- code-from-image, log-summary-date-ranges, overfull-hbox: each alternative fails the task's main
  outcome check. Not yet examined; likely bad candidates.

**Mutants: 47 lenient survivors, not yet triaged.** Survivors include equivalent mutants (all 3 in
the pilot's sqlite-db-truncate were equivalent; all 3 in regex-log were real), so mutation scores are
an upper bound on leniency until sampled.
