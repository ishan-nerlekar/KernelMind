# Terminal-Bench 2.0 verifier findings: disclosure packages

One folder per task with a confirmed lenient verifier gap (Terminal-Bench 2.0 at
`2fd12b88aafdd04a52c298e3940bcb189f9766d6`, which is still `main` as of Nov 7, 2026). None of these
is reported in the repository's issues or PRs (checked Nov 7).

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
