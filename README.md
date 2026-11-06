# KernelMind

Tools for building and **auditing** agent benchmarks whose grading you can trust, plus a benchmark of
systems-debugging tasks drawn from real production incidents.

## Headline result: verifier gaps in Terminal-Bench 2.0

`kernelmind audit` probes a task's verifier with solutions whose correct verdict is known: near misses
that each break one stated requirement, mutants of the reference solution, and alternatives that meet
every requirement differently. Run on 26 Terminal-Bench 2.0 tasks:

- **8 tasks (31%) accept a solution that is wrong by the instruction's own words.** Examples: a Coq
  "proof" that assumes the theorem as an axiom, a repository "cleaned" of a leaked secret that still
  returns it to `git show`, and a deploy hook that ignores the push and writes the expected text.
- All 16 wrong solutions were **reproduced under Terminal-Bench's own harness** (Harbor) and **reported
  upstream with test fixes**: [#92–#99](https://github.com/harbor-framework/terminal-bench-2/issues/92).
- The auditor's own error rates are measured on planted flaws: gross flaws 4/4, subtle flaws 2/7, so
  31% is a lower bound.
- Under $0.25 of model calls for the whole audit.

Full write-up: **[docs/REPORT.md](docs/REPORT.md)**. Every step and decision: [docs/AUDIT.md](docs/AUDIT.md).

## The KernelMind benchmark

20 systems-debugging tasks (Go and Python): a Wi-Fi AP control plane and GoBGP (95k lines), many
transplanting the causal chain of a real networking incident into new code, with logs, live
reproductions or git history as evidence. Every grader is validated three ways: the starter fails,
alternative correct fixes pass, and at least three plausible wrong fixes fail on the check aimed at
each. That validation method is what became the auditor.

Difficulty study: over 8 rounds and 122 attempts, the cheapest current models (Claude Haiku 5.5, GPT-6
Luna) solved every task design we tried. What didn't make tasks harder, and why, is written up in
[docs/CALIBRATION.md](docs/CALIBRATION.md).

## Quickstart

```sh
pip install -e ".[agents]"                  # Python 3.11+, Docker
kernelmind validate                         # every KernelMind task: starter fails, fixes pass, wrong fixes fail
kernelmind run --agent mini --model claude-haiku-5-5 --attempts 3 --max-cost 2

# audit someone else's benchmark (Harbor / Terminal-Bench format)
git clone https://github.com/harbor-framework/terminal-bench-2 external/tb2
kernelmind audit --tasks-dir external/tb2 --out results/audit --model claude-haiku-5-5 --max-cost 1 regex-log
audit/disclosures/repro.sh                  # re-check the 8 findings under Harbor (uv tool install harbor)
```

## Repository

```
kernelmind/          harness: tasks, Docker sandbox, validation, agents, scoring, audit
tasks/               KernelMind tasks (generated from taskgen/; edit there)
taskgen/, tools/     task generator (incident transplants, git history, planted-flaw tooling)
substrate/           apnet (own code) and GoBGP v3.37.0 (Apache-2.0), where bugs are planted
audit/disclosures/   the 8 Terminal-Bench findings: wrong solutions, issue texts, test fixes, repro.sh
docs/                REPORT (write-up), AUDIT (log), CALIBRATION (difficulty study), SPEC, TASK_FORMAT
learning/            notes written while building this
```

Terminal-Bench 2.0 is Apache-2.0 (harbor-framework/terminal-bench-2); its tasks are not vendored here,
except short derived solution scripts in `audit/disclosures/`.
