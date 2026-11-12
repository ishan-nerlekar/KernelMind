# KernelMind

Tools for building and **auditing** agent benchmarks whose grading you can trust, plus a benchmark of
systems-debugging tasks drawn from real production incidents.

## Headline result: verifier gaps in Terminal-Bench 2.0

`kernelmind audit` probes a task's verifier with solutions whose correct verdict is known: near misses
that each break one stated requirement, mutants of the reference solution, and alternatives that meet
every requirement differently. Run on 26 Terminal-Bench 2.0 tasks:

- **12 tasks (46%) accept a solution that is wrong by the instruction's own words**, each confirmed under
  Terminal-Bench's own harness (Harbor) and **reported upstream with a test fix**: issues
  [#92–#103](https://github.com/harbor-framework/terminal-bench-2/issues/92), 24 wrong solutions in all.
  Examples: a Coq "proof" that assumes the theorem as an axiom, a "cleaned" repository that still returns
  the leaked secret to `git show`, a pipeline-parallel training step that never runs the backward pass, and
  a terminal that ignores Ctrl-C. One task's own reference solution is wrong.
  Two had earlier reports elsewhere (see [audit/disclosures/README.md](audit/disclosures/README.md)); all 12 gaps are
  still present in Terminal-Bench 2.1.
- Two methods: a cheap blind auditor (near misses that each break one requirement, plus mutants; under $0.25)
  found the first 8; a strong model that **reads the tests and writes the exploit**, with every exploit run
  against the real tests, found 12 of the auditor's 14 gaps by reading, plus the other 4 tasks (about $2 for
  26 tasks).
- By manual verdict, every audited task accepts *some* wrong solution and 18 of 26 accept one an agent could
  plausibly produce (single judge; not all filed).
- The auditor's own error rates are measured on planted flaws: gross flaws 4/4, subtle flaws 2/7.
- **Terminal-Bench 4.0:** the test-reading review on 54 runnable tasks; all 24 hand-picked wrong solutions scored
  1.0 under Harbor (23 tasks). 10 were already reported, mostly by a larger audit two weeks earlier; 9 tasks look
  new; 8 filed as [#2730–#2737](https://github.com/harbor-framework/terminal-bench/issues/2730) (REPORT §3.5).
- Related work: these gaps survived Terminal-Bench's own audit of 2.0 ([Buchanan et al., 2026](https://arxiv.org/abs/2611.08417),
  28 tasks repaired, mostly strictness and drift). Prompting models to hack TB2 ([Terminal Wrench](https://arxiv.org/abs/2606.08960))
  found 13 tasks, only 2 of them among these 12. Full positioning, including SWE-bench test-adequacy work, in REPORT §5.

Full write-up: **[docs/REPORT.md](docs/REPORT.md)**. Every step and decision: [docs/AUDIT.md](docs/AUDIT.md).
Blog post: [The grader said yes](https://thegradersaidyes.hashnode.dev/the-grader-said-yes-auditing-terminal-bench-2-0-with-near-miss-solutions).

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
audit/disclosures/repro.sh                  # re-check the TB2 findings under Harbor (uv tool install harbor)
```

## Repository

```
kernelmind/          harness: tasks, Docker sandbox, validation, agents, scoring, audit
tasks/               KernelMind tasks (generated from taskgen/; edit there)
taskgen/, tools/     task generator (incident transplants, git history, planted-flaw tooling)
substrate/           apnet (own code) and GoBGP v3.37.0 (Apache-2.0), where bugs are planted
audit/disclosures/   the 12 Terminal-Bench 2.0 findings: wrong solutions, issue texts, test fixes, repro.sh
audit/disclosures-tb4/ the Terminal-Bench 4.0 findings: issue texts, wrong solutions, test fixes
docs/                REPORT (write-up), AUDIT (log), CALIBRATION (difficulty study), SPEC, TASK_FORMAT
```

## License

Apache-2.0 (see [LICENSE](LICENSE)); third-party notices in [NOTICE](NOTICE). GoBGP and Terminal-Bench 2.0 are
also Apache-2.0. Terminal-Bench tasks are not vendored here, except short derived solution scripts in
`audit/disclosures/`.
