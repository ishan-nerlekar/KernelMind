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

## T4 results (Nov 7): the auditor's own error rates

Run: `python3 tools/audit_planted.py --model claude-haiku-5-5 --max-cost 1` on the Mac, 11 planted
flaws, $0.05 of generation.

| | Detected | Found by |
|---|---|---|
| Gross flaws (the weakened grader also passes the untouched starter) | **4/4** | the starter itself, plus 2–3 near misses each |
| Subtle flaws (the starter still fails) | **2/7 (29%)** | ap-mlo-inactivity (near-1-symptom, near-3-hardcoded), seq-wraparound (near-2-symptom) |

Missed subtle flaws: config-override-precedence, lease-renew-gateway, peer-timeout-flap,
ssid-dva-global-vlans, x-lease-oblique. In each, the planted flaw only lets through one *specific*
wrong fix (for example, updating the gateway but not the DNS servers), and none of the 4 model-written
near misses or ≤6 mutants made that mistake.

**What this means for the Terminal-Bench numbers:** the auditor finds gross gaps reliably but misses
most narrow ones, so 7 of 24 tasks with confirmed gaps is a **lower bound**. Obvious improvements to
test: more near misses per task, and one near miss per instruction sentence instead of per category.

### Suspects against KernelMind's sound graders (18)

Running the same candidates against KernelMind's original tests is also an audit of KernelMind itself.

| Verdict | Count | Details |
|---|---|---|
| Real gap in KernelMind's tests | 2 | peer-timeout-flap: a NotFound result sets `Stale = true` and no test checks `Stale` after NotFound (mutant). seq-wraparound: `Next(65535)` returns 1 instead of wrapping to 0 and no test checks the wrap (near-4; minor) |
| Possible strictness in KernelMind | 1 | peer-timeout-flap alt-2 fixes the symptom in the caller (a timeout is never reported to the tracker as a miss) instead of in `peer.Tracker`; the hidden tests unit-test the tracker, so a caller-level fix fails. Needs a decision: is the tracker the only acceptable fix location? |
| Equivalent mutants | 2 | seq-wraparound `> 0` → `>= 0` (with `a != b` never 0); neigh-roam-flush per-interface counter (no longer observable after the fix) |
| Near misses that weren't wrong | 6 | the claimed flaw didn't apply (config-override isolation default already `false`; neigh-roam capacity check `>=` not present), didn't exist (rate-counter "packet counters": apnet has none; radio "second push path": there isn't one), or is unobservable (neigh-roam near-1, near-2: per-interface counts) |
| Alternatives that were wrong | 7 | 3 don't compile; 3 fail the behavior the task is about; 1 hangs (ap-mlo alt-2, probably a lock taken twice) |

**Raw suspects are mostly noise on sound graders:** 3 of 18 were worth a human's attention. On
Terminal-Bench's graders the model-written lenient suspects confirmed at a much higher rate (11 of
17 including the pilot), consistent with those graders having real gaps. Either way, every finding
needs the manual confirmation step; the auditor ranks where to look, it doesn't decide.

KernelMind follow-ups (log in CHANGELOG when done): add a `Stale`-after-NotFound check to
peer-timeout-flap and a wrap check for `Next` to seq-wraparound; decide on the caller-level fix.

## Rerun of 3 broken baselines (Nov 7)

- **prove-plus-comm: now graded, with a confirmed lenient finding.** The working-directory fix
  worked (the image's WORKDIR is `/workspace`). A model-written near miss "proves" commutativity of
  addition by declaring `Axiom plus_comm_axiom : forall n m : nat, n + m = m + n.` and applying it,
  which proves nothing. The tests check only that `plus_comm.v` contains the theorem text, `Proof.`
  and `Qed.`, doesn't contain the lowercase string `admit`, and compiles. They never check axioms,
  which Coq's `Print Assumptions plus_comm.` would reveal. (Untested: since the `admit` check is
  case-sensitive, `Admitted.` plus a `Qed.` inside a comment may also pass.) Its surviving mutant
  deletes one `- simpl.` bullet; very likely still a valid proof (equivalent).
- **git-multibranch: still broken, harness cause found.** The reference solution runs `tmux`, which
  the image doesn't include; Harbor runs agents inside tmux, so the task silently relies on it.
  The harness now installs tmux for external tasks whose reference uses it. Rerun needed.
- **fix-git: environment rot.** The image build clones `github.com/TheMikeMerrill/personal-site`,
  which now asks for credentials (deleted or private), so the task can no longer be built from
  source. The task also names a prebuilt image (`alexgshaw/fix-git:20251031`), which Harbor
  presumably runs, so it probably still works there. The harness now falls back to a task's prebuilt
  image when the source build fails. Rerun needed.

**Running total: 25 graded tasks, 8 with at least one confirmed lenient gap (32%).** Environment
findings, separate from grading: `build-pmars` (the reference fails at run time: pinned package
gone) and `fix-git` (the source build fails: cloned repository gone).

### Second rerun (Nov 7)

- **fix-git: graded on its prebuilt image; no findings.** Both "strict" suspects are wrong
  alternatives: they take line 4 of `git reflog` (newest first), while the reference takes line 4 of
  `.git/logs/HEAD` (oldest first), so they merge a different commit and fail the content checks
  correctly. The surviving mutant deletes `git checkout master`, which is redundant because setup
  already leaves the repo on master (equivalent).
- **git-multibranch: excluded.** With tmux installed, the reference gets through its own script, but
  the grader fails without writing test results; it probably relies on more of Harbor's runtime (the
  git server's SSH setup). Not investigated further.

**Final T5 tally: 26 graded tasks (4 pilot + 22), 8 with at least one confirmed lenient gap (31%).**
Excluded: break-filter-js-from-html, tune-mjcf, git-multibranch (harness or hardware), build-pmars
(environment drift, a finding of its own).

## Already known? Terminal-Bench 2.0 tracker check (Nov 7)

All 91 issues and PRs (open and closed) on `harbor-framework/terminal-bench-2`, read through the
public GitHub API.

| Our finding | Already reported? |
|---|---|
| build-pmars: reference fails (pinned `dpkg-dev` gone) | **yes**: #59 "`build-pmars` failing with oracle solution" (open) |
| git-multibranch: reference needs tmux | **yes**: #52 "`solve.sh` calls tmux without install" (open) |
| fix-git: source build clones a repository that's gone | no (#63/#64 and #30 are about other fix-git details; #66 proposes digest-pinning `docker_image`) |
| configure-git-webserver: hardcoded `hello world` passes | **no**. Open PR #39 rewrites this verifier's auth, but its new `verify.sh` still pushes and checks exactly `hello world`, so the gap stays |
| regex-log, git-leak-recovery, db-wal-recovery, modernize-scientific-stack, cobol-modernization, sparql-university, prove-plus-comm | **no** issues or PRs mention these tasks |

So **all 8 lenient-gap findings are unreported**; 2 of our 3 environment findings already were.

The tracker also calibrates the auditor. People are filing exactly this class of report (#67
"make-doom-for-mips passes without a DOOM binary built", #89 on filter-js-from-html, #62
gpt2-codegolf), which confirms the problem matters to the community. Two reports are on tasks we
audited and found nothing: #85 says raman-fitting's verifier locks unstated conventions (a
*strictness* claim; our 0 accepted alternatives there were all broken candidates, so we never tested
it), and #84 says sanitize-git-repo's verifier crashes when history is rewritten (an alternative
our generator didn't produce). Both point at the auditor's weak side: alternatives (strictness
probes) are much harder to generate correctly than near misses.

## T7 disclosure packages (Nov 7)

`audit/disclosures/`: for each of the 8 tasks, the wrong solutions, a draft issue, and a suggested
test fix. 7 of 8 fixes were checked locally: the reference passes, each wrong solution fails. That
needed Coq 8.18, GnuCOBOL 3.1 and rdflib in the workspace. While checking prove-plus-comm, a second
bypass was **confirmed** against the current tests: `Admitted. (* Qed. *)` passes, because the
`admit` check is case-sensitive and `Qed.` may sit in a comment. `repro.sh` re-checks every finding
under Harbor's oracle agent before filing.

## Confirmed under Harbor, and filed (Nov 7)

`audit/disclosures/repro.sh` on the Mac with Harbor 0.25: for all 8 tasks the reference solution and
**every** wrong solution scored reward 1.0 with Harbor's oracle agent (21 trials). All 8 findings are
confirmed under Terminal-Bench's own harness.

| Task | Issue |
|---|---|
| regex-log | [#92](https://github.com/harbor-framework/terminal-bench-2/issues/92) |
| git-leak-recovery | [#93](https://github.com/harbor-framework/terminal-bench-2/issues/93) |
| prove-plus-comm | [#94](https://github.com/harbor-framework/terminal-bench-2/issues/94) |
| configure-git-webserver | [#95](https://github.com/harbor-framework/terminal-bench-2/issues/95) |
| db-wal-recovery | [#96](https://github.com/harbor-framework/terminal-bench-2/issues/96) |
| modernize-scientific-stack | [#97](https://github.com/harbor-framework/terminal-bench-2/issues/97) |
| cobol-modernization | [#98](https://github.com/harbor-framework/terminal-bench-2/issues/98) |
| sparql-university | [#99](https://github.com/harbor-framework/terminal-bench-2/issues/99) |

All 8 filed by Ishan on Nov 7, 2026.

## Two follow-up experiments (planned Nov 7, before any results)

### E1: does a QA reviewer that reads the tests find these gaps?
`tools/qa_baseline.py`: a reviewer model gets what a QA agent or human reviewer would (instruction, tests,
environment files, reference solution) for each of the 26 graded tasks and lists up to 6 ways a wrong
solution could pass, each with a script. It reads the tests; it executes nothing. Reviewers:
`claude-haiku-5-5` (the auditor's own generator) and two frontier models, `claude-opus-5-5` and
`gpt-6.1-sol`. Their training data predates issues #92–#99.

Metrics, fixed now:
- **Recall on the 14 known gaps** (`audit/qa/known_gaps.json`), judged by hand: a flag matches if it names the
  same unchecked requirement and a wrong solution that would exploit it. This ground truth is biased toward
  what the auditor finds, so it can't show the auditor is better; it shows what review alone misses.
- **The other direction:** flags on the 18 tasks with no known gap. For the best reviewer, its scripts are run
  against the tests (`grade`); a passing script that is wrong by the instruction's words is a gap the
  auditor missed. Same manual confirmation as before.
- Flags raised, and cost.

### E2: one near miss per requirement
Subtle recall was 2/7 with 4 near misses per task. New mode `--near-miss-mode requirement`: the model first lists
the instruction's checkable requirements (at most 12, cached so both arms share them), then writes one near miss
per requirement. Control arm `repeat`: the original category prompt, called until it yields the same number of
near misses, so the comparison is targeting, not volume. Both run on the 7 subtle planted flaws only, near
misses only (mutants found none of them), with the same regrade against the sound tests.

Prediction: requirement mode beats repeat on subtle recall, because each subtle flaw lets through one specific
requirement's violation (gateway updated but not DNS, and so on). If repeat does as well, the gain is volume.

## E1 results, part 1 (Nov 7): reviewers reading the tests

| Reviewer | Known gaps found | Flags raised (26 tasks) | Tasks with no flags | Cost |
|---|---|---|---|---|
| claude-haiku-5-5 | 9/14 | 61 | 0 | $0.07 |
| claude-opus-5-5 | 12/14 | 82 | 0 | $2.16 |

`gpt-6.1-sol` was not run (the OpenAI account had no credits). Judgments: `audit/qa/judged-<model>.json`.

- **A frontier reviewer that is asked the right question sees most of these gaps by reading.** Opus missed
  only `git-leak-recovery` "recoverable" (it flagged a different hiding place, a plaintext copy in
  `.git/description`) and `regex-log` "coverage" (May and octets 250–254). Haiku missed all three regex-log gaps,
  the commit-message check and the exactly-10 boundary.
- So the gaps were not hard to see. They survived because nobody asked a reviewer to *construct a wrong
  solution that passes*. Terminal-Bench's QA includes LLM checks of instruction/test consistency; the framing of
  this prompt, not the model, is likely the difference. (Not tested: we don't have their exact prompt.)
- **Neither reviewer ever said "the tests look sound"**: every task got 1–6 flags. Reading alone can't say which
  flags are real. Next step: run the Opus reviewer's scripts against the tests (`qa_baseline.py grade`) to
  measure how many of its 82 claims hold, and whether any are gaps the auditor missed.
- Candidate new gaps raised by both reviewers, to check after grading: `sparql-university` (the query, including
  the reference's, counts students across all of a professor's departments instead of per department; the data
  can't tell the difference), `db-wal-recovery` (values of ids 3–11 are never checked, so fabricated data passes),
  `cobol-modernization` (no insufficient-funds or buyer-equals-seller case).

## E1 results, part 2 (Nov 8): running the Opus reviewer's scripts

`qa_baseline.py grade --model claude-opus-5-5`: each of the 82 flags' scripts graded by the task's own tests.
**80 passed, 2 were caught.** (`configure-git-webserver`'s reference failed in this run, a known flaky
network step; its flags were graded anyway.) Passing the tests only means the tests accept it, so every flag
got a manual verdict against the instruction (`audit/qa/verdicts-claude-opus-5-5.json`). 13 scripts were read
in full; all 13 did what their flag claimed.

| Verdict | Flags | Meaning |
|---|---|---|
| plausible | 32 | wrong by the instruction's explicit words; a mistake or shortcut an agent could make without seeing the tests |
| deliberate | 35 | wrong, but only as intentional gaming: decoys, sabotage, overwriting the checker's inputs |
| test-aware | 11 | hardcodes values only the hidden tests reveal |
| debatable | 2 | the instruction isn't explicit enough to call it wrong |
| caught | 2 | the tests reject it |

- **Every one of the 26 tasks accepts at least one wrong solution; 18 (69%) accept a plausible one**, against 8
  (31%) found by the original auditor. 25 of 26 accept one that needs no knowledge of the hidden tests.
- Examples the auditor missed: `torch-pipeline-parallelism` accepts a pipeline that never runs a backward pass
  (the test compares only the hooks that fired) and an interleaved schedule instead of AFAB (the order check
  walks dict insertion order); `torch-tensor-parallelism` accepts a row-parallel layer that adds the bias once per
  rank; `headless-terminal` accepts a terminal that drops Ctrl-C; `large-scale-text-editing` accepts macros that
  use Vimscript functions it forbids; `sqlite-db-truncate` accepts recovering 7 of 8 rows; `fix-git` accepts
  copying the files without merging; `openssl-selfsigned-cert` accepts a CA-signed (not self-signed) certificate.
- **The `sparql-university` reference solution is itself wrong.** It groups by professor only, so it counts
  students across all of a professor's departments instead of requiring one department with more than 10. On the
  test graph plus one professor with 6 students in each of two departments, the reference returns that professor
  and a per-department query doesn't (`audit/qa/probe_sparql_split_departments.py`). The test data can't tell.
- For Opus, execution filtered almost nothing (80 of 82 claims held). Its value was turning claims into
  reproducible evidence. Haiku's scripts were not graded, so its precision is unknown.
- Caveats: one judge (me), verdicts on 69 flags made from the flag text and the tests rather than the script;
  "plausible" vs "deliberate" is a judgement call. None of the new findings is reproduced under Harbor or filed.

## E2 results (Nov 8): one near miss per requirement did not help

| Arm (7 subtle planted flaws, Haiku) | Near misses graded | Detected |
|---|---|---|
| original: 4 per task, one per category | 28 | 2/7 |
| requirement: one per requirement (6–12 per task) | 54 (+5 broken) | 2/7 |
| repeat: original prompt, same count as requirement | 59 | **4/7** |

The prediction was wrong. Targeting requirements found nothing new; more near misses from the original prompt
found two more (`ssid-dva-global-vlans`, `x-lease-oblique`). With 7 flaws the difference between 2 and 4 is
within noise (Fisher exact p ≈ 0.6), so the honest reading is "no evidence that targeting helps".

Why targeting failed, from the candidates: the model *did* write the right violation, but broke something else
too. In `lease-renew-gateway`, near-5 "never refreshes the DNS resolver" is exactly the planted flaw's witness,
yet it also failed `TestRenewPublishesNewGateway`; in `x-lease-oblique`, near-8 and near-9 (DNS not refreshed) also
failed `TestAcquirePublishes`. A near miss only exposes a subtle gap if it is wrong in *exactly* one way. Next
idea (not run): build near misses as one-hunk edits of the reference patch instead of rewritten scripts.

Combined with E1: the cheapest way to raise recall is not a smarter blind generator but letting a strong model
read the tests and write the exploit, then running it.

## Batch 2 filed (Nov 7)

| Task | Finding | Link |
|---|---|---|
| headless-terminal | `test_cancel_command` passes without Ctrl-C working | [#100](https://github.com/harbor-framework/terminal-bench-2/issues/100) |
| openssl-selfsigned-cert | CA-signed cert, key mode 077, unrelated PEM key pair, CN/O outside the subject all pass | [#101](https://github.com/harbor-framework/terminal-bench-2/issues/101) |
| sparql-university | reference counts students across departments; correction to #99's suggested test (expected values were from the agent-visible graph) | [comment on #99](https://github.com/harbor-framework/terminal-bench-2/issues/99#issuecomment-6702427766) |

Both issues were confirmed under Harbor (wrong solutions 1.0) and their fixes validated under Harbor
(`repro.sh --fixed`: reference 1.0, wrong solutions 0.0).

The torch pair needed reruns: the first Harbor trials all failed downloading PyTorch at verify time, so
`repro.sh` gained an opt-in `UV_HTTP_TIMEOUT` (install step only). With it, both were confirmed (wrong
solutions 1.0 on the current tests) and both fixes validated (reference 1.0, wrong solutions 0.0; the
torch-tensor fix fails the wrong solution on exactly `test_row_parallel_linear[2-True]` and `[4-True]`).

| Task | Finding | Link |
|---|---|---|
| torch-pipeline-parallelism | a step with no backward pass, or an interleaved schedule, passes | [#102](https://github.com/harbor-framework/terminal-bench-2/issues/102) |
| torch-tensor-parallelism | bias is always zero in the tests, so a bias added once per rank passes | ready to file |
