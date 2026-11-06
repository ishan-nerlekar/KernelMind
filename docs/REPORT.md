# Auditing benchmark verifiers with near-miss solutions: findings on Terminal-Bench 2.0

Ishan Nerlekar · November 2026 · code and data: this repository

## Summary

A benchmark score is only as good as its verifier. A verifier that accepts wrong solutions inflates
scores; one that rejects correct solutions deflates them. Both are hard to see by reading tests.

This report describes a cheap, mostly automated way to probe verifiers, and what it found on
**Terminal-Bench 2.0**, a widely used benchmark of agentic terminal tasks:

- For each task, generate solutions whose correct verdict is known: **near misses** that each break
  one stated requirement (should fail), **mutants** of the reference solution (should fail) and
  **alternatives** that meet every requirement differently (should pass). Then run the task's own
  tests on all of them.
- On 26 graded tasks, **8 (31%) accepted at least one solution that is wrong by the instruction's own
  words**: 16 confirmed wrong solutions, including a proof that proves nothing and a "cleaned" repository
  that still contains the leaked secret. All were **reproduced under the benchmark's own harness**
  (Harbor) and **reported upstream with test fixes**: issues
  [#92–#99](https://github.com/harbor-framework/terminal-bench-2/issues/92).
- Model cost for the whole audit was under $0.25; the real cost is container time.
- The auditor's own error rates were measured on planted flaws: it finds gross verifier flaws reliably
  (4/4) but misses most subtle ones (2/7), and its raw suspects need human confirmation. The 31% is
  therefore a lower bound.

The audit grew out of KernelMind, a systems-debugging benchmark built from patterns in real production
incidents. Its main result was negative (the cheapest current models solve all 20 of its tasks), and
its grading method became the auditor. Both are described below.

## 1. Method

### 1.1 Candidates

For each task, `kernelmind audit` writes candidates into a copy of the task and grades each one in a
fresh container with the task's own `tests/test.sh`.

| Candidate | Made by | Expected verdict | Unexpected verdict means |
|---|---|---|---|
| Mutant: one changed number, comparison or boolean in the reference `solve.sh`, or one deleted shell step | code, deterministic per task | fail | *lenient suspect*, unless the mutant is equivalent |
| Near miss: breaks exactly one instruction sentence, in one of six categories (partial, edge case, symptom-only, over-broad, hardcoded, wrong format) | Claude Haiku 5.5, shown the instruction and the reference solution, never the tests | fail | *lenient suspect* |
| Alternative: meets every requirement in a different way | same model | pass | *strict suspect* |

Each near miss must quote the instruction sentence it violates. The six categories come from the
wrong-fix controls used to validate KernelMind's own graders (§4). A model-written candidate whose own
script fails is counted as broken and says nothing about the verifier. The model never sees the tests,
so candidates represent plausible mistakes rather than test-gaming.

### 1.2 Confirmation

A suspect is not a finding. Each was checked by hand: does the candidate really violate the quoted
requirement (models often claim flaws their code doesn't have), and why do the tests miss it? Where
possible, the violation was demonstrated with a differential probe: an input the instruction decides,
on which the reference and the candidate disagree. Confirmed findings were then reproduced under
**Harbor 0.25**, Terminal-Bench's own harness: each wrong solution replaced `solution/solve.sh` and
was run with Harbor's `oracle` agent (`audit/disclosures/repro.sh`). All 21 trials (8 references and
13 wrong solutions) scored reward 1.0.

### 1.3 Sample

Terminal-Bench 2.0 has 89 tasks, at commit `2fd12b8` (still `main` on Nov 7, 2026). The audit used a
5-task pilot plus 25 tasks sampled with a fixed seed from the 33 that pass rules fixed before any
results: no GPU, no model training, a light image, a short reference solution and no large downloads
(`docs/AUDIT.md`). Of these 30, **26 were graded**; 4 were excluded (3 need parts of Harbor's runtime
or specific hardware, and 1 has a broken reference solution, §2.3).

## 2. Findings on Terminal-Bench 2.0

### 2.1 Confirmed lenient verifiers

| Task | Wrong solution that passes | Why the tests miss it | Issue |
|---|---|---|---|
| prove-plus-comm | proves `n + m = m + n` from an `Axiom` stating it; also `Admitted.` with `Qed.` in a comment | tests check strings and that the file compiles; nothing asks Coq for the proof's assumptions | [#94](https://github.com/harbor-framework/terminal-bench-2/issues/94) |
| git-leak-recovery | leaves the secret recoverable (`git show <dangling commit>`); rewrites every commit message | the "unreachable objects" check prints dangling *commit headers*, not the blob holding the secret; message check is a substring match | [#93](https://github.com/harbor-framework/terminal-bench-2/issues/93) |
| configure-git-webserver | the deploy hook ignores the push and writes a literal `hello world` | the verifier pushes exactly the instruction's example and checks for exactly that | [#95](https://github.com/harbor-framework/terminal-bench-2/issues/95) |
| modernize-scientific-stack | edits the script marked "DO NOT MODIFY"; omits the required version constraints | only the script's output and the dependency file's existence are checked | [#97](https://github.com/harbor-framework/terminal-bench-2/issues/97) |
| db-wal-recovery | writes the right JSON but never fixes the WAL file (step 1 of the instruction) | only the JSON is checked | [#96](https://github.com/harbor-framework/terminal-bench-2/issues/96) |
| cobol-modernization | a Python port without the COBOL program's seller-owns-book check | all three graded transactions are valid sales | [#98](https://github.com/harbor-framework/terminal-bench-2/issues/98) |
| regex-log | rejects Feb 29 (explicitly allowed); accepts April 31; ignores May; rejects octet 250 | the "invalid date" samples also contain an invalid IP, so they test the IP, not the date; no sample covers the rest | [#92](https://github.com/harbor-framework/terminal-bench-2/issues/92) |
| sparql-university | counts the UK as an EU member in 2025; reads "more than 10" as `>= 10` | the graph has no `GB` and no department with exactly 10 students | [#99](https://github.com/harbor-framework/terminal-bench-2/issues/99) |

15 of the 16 wrong solutions came from the auditor (12 model-written near misses and 3 mutants of
`regex-log`). The `Admitted.` variant was found by hand
while checking the proposed fix for `prove-plus-comm`. Each issue includes a test change; 7 of the 8
were validated locally (the reference passes, every wrong solution fails), using Coq 8.18, GnuCOBOL 3.1
and rdflib where needed. Severity varies: the axiom proof, the recoverable secret and the hardcoded
deploy are serious; the SPARQL boundary cases are minor.

### 2.2 Five recurring causes

1. **Stated requirements never tested.** "DO NOT MODIFY", version constraints, "fix the WAL file",
   "commit messages remain untouched".
2. **One fixed input that lacks the deciding case.** The COBOL rejection path, a non-EU country,
   exactly 10 students, February 29.
3. **Test input identical to the instruction's example**, so hardcoding passes (`hello world`).
4. **Confounded negative samples.** A sample meant to break rule A also breaks rule B, so it can't
   detect a mistake in A.
5. **Checking the wrong object, or checking text instead of meaning.** Commit headers instead of their
   contents; the string `Qed.` instead of what Coq actually accepted.

All five are invisible when the only solutions ever graded are the reference and a few agent attempts.
They show up immediately when you grade solutions that are *almost* right.

### 2.3 Environment drift (separate from verifier quality)

- `build-pmars`: the reference solution pins `dpkg-dev=1.22.21`, which Debian no longer serves, so the
  oracle fails today. Already reported as #59.
- `fix-git`: the image build clones a GitHub repository that no longer exists. The task still runs from
  its prebuilt image, which Harbor uses, but it can't be rebuilt from source. Not reported elsewhere.

### 2.4 No confirmed strict verifiers

9 model-written alternatives failed. 4 were verified to be wrong (2 SPARQL queries with different
answers, 2 `fix-git` scripts that merge the wrong commit), 2 in `headless-terminal` are unresolved
(either wrong or failing timing-sensitive tests), and 3 were not examined. None was confirmed as a
correct solution the verifier rejects. This says more about the auditor than about the benchmark: a
correct alternative is much harder to generate than a near miss. Others have since reported strictness and
crash issues on two tasks we audited without finding anything (#84, #85), so this side remains a
blind spot.

## 3. How good is the auditor?

### 3.1 Recall on planted flaws

On 11 KernelMind tasks, we disabled the tests that catch one known wrong fix, so the verifier had a
known flaw, then audited the weakened tasks and regraded the same candidates against the original
tests (`tools/plant_flaws.py`, `tools/audit_planted.py`).

| Planted flaw | Detected |
|---|---|
| Gross (the weakened verifier also accepts the untouched starter) | 4/4 |
| Subtle (only one specific wrong fix gets through) | 2/7 |

With four near misses per task, the model rarely makes the one specific mistake a subtle flaw lets
through. More near misses, or one per instruction sentence, is the obvious next experiment.

### 3.2 Precision of raw suspects

On Terminal-Bench, 12 of 18 model-written lenient suspects were confirmed (67%). On KernelMind's own
graders, which were validated against at least three wrong fixes each, 3 of 18 suspects were worth
attention: 2 small real gaps in KernelMind's tests and 1 open question about where a fix may live.
The rest were equivalent mutants, near misses whose claimed flaw wasn't in their code, and broken
alternatives. **The auditor ranks where to look; a human still decides.** 47 surviving mutants on
Terminal-Bench were not triaged; in the pilot, 3 of 6 were real and 3 equivalent.

### 3.3 Cost

Generation cost $0.16 for the Terminal-Bench audit and $0.05 for the planted-flaw study. Grading took
roughly 10–15 minutes of container time per task on a laptop (Apple Silicon, some images emulated).

## 4. Background: KernelMind and the difficulty study

KernelMind started as a benchmark of systems-debugging tasks: 20 tasks in a small Wi-Fi control plane
(apnet) and in GoBGP (95k lines), many transplanting the causal chain of a real production networking
incident into new code, so that the buggy code isn't public. Every task's grader is validated three
ways: the starter fails, alternative correct fixes pass, and at least three plausible wrong fixes fail
on the specific check aimed at each.

To set difficulty, two cheap models kept off any leaderboard (Claude Haiku 5.5 and GPT-6 Luna) probed
each new task design. Over 8 rounds and 122 attempts (about $1.10), they solved every task, whatever the
lever: codebase size, novel code, no textual clues, decoys, two interacting faults behind a live
reproduction, and a regression introduced by an earlier fix, with git history. Trajectories showed
why: they search for every term in the evidence at once, re-run reproductions after each fix, and read
why a change was made before reverting it. Our working hypothesis is that these models fail when
information is *missing*, not when it is spread out or disguised. We have not tested it yet.

The negative result is in `docs/CALIBRATION.md`. The validation method behind it is what this report
is about.

## 5. Limitations

- 26 of 89 tasks, chosen by rules that exclude heavy tasks; "31% of tasks" may not hold for the rest.
- One generator model, four near misses and up to six mutants per task. Recall on subtle flaws is low,
  so the true rate of lenient verifiers is likely higher.
- Confirmation is manual judgement against the instruction's wording; we report only cases where the
  instruction is explicit.
- Strictness is barely covered (§2.4).
- Some grading ran on Apple Silicon with emulated images; the findings themselves were re-confirmed
  under Harbor.

## 6. Reproducing

```sh
pip install -e ".[agents]" && uv tool install harbor
git clone https://github.com/harbor-framework/terminal-bench-2 external/tb2   # pinned at 2fd12b8
kernelmind audit --tasks-dir external/tb2 --out results/audit --model claude-haiku-5-5 --max-cost 1 regex-log
audit/disclosures/repro.sh            # re-checks the 8 findings under Harbor
python3 tools/audit_planted.py --model claude-haiku-5-5 --max-cost 1     # auditor recall on planted flaws
```

Per-task results, triage notes and every intermediate decision are in `docs/AUDIT.md`.
