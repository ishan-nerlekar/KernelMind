# Terminal-Bench 2.0 verifier findings: disclosure packages

One folder per task with a confirmed lenient verifier gap (Terminal-Bench 2.0 at
`2fd12b88aafdd04a52c298e3940bcb189f9766d6`, which is still `main` as of Nov 7, 2026). Checked against the terminal-bench-2 tracker on Nov 7. A later check (Nov 7) of the
Terminal-Bench 2.1 repo and the main `harbor-framework/terminal-bench` repo found two earlier reports:
configure-git-webserver (#95) matches terminal-bench-2-1 PR #37 (July 2026) and Terminal Wrench (Zhong et al.,
2026); the version-constraint half of modernize-scientific-stack (#97) matches terminal-bench #2173 (Oct 2026).
The other ten have no earlier report. All 12 gaps are still present in Terminal-Bench 2.1 (11 tasks' tests are
unchanged; the other two changes don't close the gaps).

Each folder has:
- `<case>/solve.sh`: a wrong solution that the task's tests accept
- `ISSUE.md`: the draft issue (requirement, what passes, why, suggested fix)
- `test_fix_addition.py` or `test_fix.patch`: the suggested test change, checked locally against the
  reference solution (passes) and the wrong solutions (fail), except configure-git-webserver (not run)

`repro.sh` reproduces everything under Harbor, Terminal-Bench's own harness: it runs each task's
reference solution and each wrong solution with Harbor's `oracle` agent. A finding is confirmed when
both score 1.

| Task | Wrong solutions | Suggested fix checked locally |
|---|---|---|
| regex-log | Feb limited to 28 days; April 31 accepted | yes |
| git-leak-recovery | secret left in a dangling commit; commit messages rewritten | yes |
| configure-git-webserver | hook writes a literal "hello world" | no (needs ssh/nginx) |
| db-wal-recovery | WAL left encrypted | yes |
| modernize-scientific-stack | no version constraints; "DO NOT MODIFY" script edited | yes |
| cobol-modernization | Python port without the ownership check | yes (expected files from GnuCOBOL 3.1) |
| sparql-university | GB counted as EU; `>= 10` | yes (rdflib) |
| prove-plus-comm | theorem assumed as an axiom; `Admitted.` + `(* Qed. *)` | yes (Coq 8.18) |

## Batch 2 (Nov 8): found by the test-reading reviewer (docs/AUDIT.md, E1)

Wrong solutions written by Claude Opus 5.5 while reviewing the tests (`tools/qa_baseline.py`), then judged
by hand. Not in the tracker as of Nov 8.

| Task | Wrong solutions | Suggested fix checked |
|---|---|---|
| torch-pipeline-parallelism | no backward pass at all; interleaved schedule instead of AFAB | under Harbor (`repro.sh --fixed`) |
| torch-tensor-parallelism | RowParallelLinear adds the bias once per rank | under Harbor (`repro.sh --fixed`) |
| headless-terminal | terminal that drops Ctrl-C | locally (pytest + tmux), 5/5 |
| openssl-selfsigned-cert | CA-signed cert; key mode 077; PEM with an unrelated key pair; CN/O only in OU/SAN | locally (pytest + OpenSSL 3) |
| sparql-university (comment on #99) | the reference itself counts students across departments; #99's suggested test had expected values from the wrong graph | locally (rdflib) |

`repro.sh --fixed <task>` applies `test_fix.patch` before running: the reference should score 1 and every
wrong solution 0. `_local/check.sh` runs a task's tests natively (no Docker) for quick checks.
