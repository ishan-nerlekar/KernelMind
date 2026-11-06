# Draft issues for Terminal-Bench 2.0 (for review before filing)

---

## regex-log

**Title:** regex-log: two "invalid date" samples are rejected for their IP, so the date rules (and Feb 29) are never tested

**What the instruction requires**
> Assume that February can have up to 29 days in all years, without distinguishing leap years from non-leap years.

and, implicitly, that only real calendar dates match (April has 30 days).

**What passes today**
Both of these regexes pass `test_regex_matches_dates`:
- `feb-28-only/solve.sh`: the reference regex with February limited to `2[0-8]`. It rejects `2021-02-29`, which the instruction explicitly allows.
- `april-31-accepted/solve.sh`: the reference regex with 30-day months accepting day 31. It matches `2020-04-31`.

**Why the tests miss it**
- The samples commented `# N: invalid date 30th February` and `# N: invalid date 31th April` both use IP `172.16.0.256`, which is invalid, so they are rejected for the IP. With a valid date (`2000-04-10`) they are still rejected. They never exercise the date rule.
- No sample contains a February 29, a May date or a last octet of 250–254 on a matching line, so regexes that get these wrong also pass. (We saw passing variants that drop month `05` and reject octet `250`.)

**Suggested fix** (`test_fix.patch`): give the two samples a valid IP (`172.16.0.25`) and add `Leap-day login from 10.0.0.1 on 2021-02-29` and `Login from 10.0.0.250 on 2020-05-20` as matching lines.
Checked locally: the reference regex passes the patched test; both regexes above fail it.

---

## git-leak-recovery

**Title:** git-leak-recovery: the secret can stay in the repo (blob of a dangling commit) and commit messages can be rewritten, and both pass

**What the instruction requires**
> 2. clean up the secret in that repo to make sure it cannot be found anywhere in that repo.
> 3. make sure irrelevant files and commit messages remain untouched.

**What passes today**
- `near-1-partial/solve.sh` recovers the secret and does nothing else. Afterwards `git -C /app/repo show bd81824` still prints `secret[lost_and_found_in_git]`, and the tests pass.
- `near-4-over-broad/solve.sh` rewrites every commit message to `[sanitized] chore: init …`. The tests pass.

**Why the tests miss it**
- `test_no_secrets_in_unreachable_objects` runs `git cat-file -p` on each *dangling* object listed by `git fsck --lost-found`. The dangling object here is a commit, and `cat-file -p` of a commit prints its header (tree, parent, author, message), not the file contents. The blob holding the secret is not itself dangling, since the dangling commit's tree references it, so it is never inspected. Objects still referenced by the reflog are never "dangling" either.
- `test_good_commits_preserved` checks that one message *contains* `chore: init e665…`, so prefixed or reworded messages pass.

**Suggested fix** (`test_fix_addition.py`): check that no object in the store contains the secret (`git cat-file --batch-all-objects --batch`), and that every commit message equals the original exactly.
Checked locally: the reference solution passes both; near-1 fails the first and near-4 fails the second.

---

## configure-git-webserver

**Title:** configure-git-webserver: a post-receive hook that ignores the push and writes a literal "hello world" passes

**What the instruction requires**
> And have this data then be pushed to a webserver running on port 8080

i.e. whatever is pushed gets deployed.

**What passes today**
`near-4-hardcoded/solve.sh` installs a hook whose whole body is `echo "hello world" > /var/www/html/hello.html`. It never deploys the pushed content, and it passes.

**Why the tests miss it**
`verify.sh` pushes exactly the instruction's example (`echo 'hello world' > hello.html`) and checks for exactly `hello world`. Open PR #39 rewrites this verifier's auth, but its new `verify.sh` still pushes and checks `hello world`, so the gap remains with it merged.

**Suggested fix:** push content the agent can't predict and check that it is served, e.g.
```bash
TOKEN="deploy-$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"
echo "$TOKEN" > hello.html   # instead of 'hello world'
...
[ "$(curl -s http://localhost:8080/hello.html)" = "$TOKEN" ]
```
A second push with different content would also catch hooks that deploy only once.
Not run locally (the verifier needs the full ssh/nginx setup); the reasoning is above.

---

## db-wal-recovery

**Title:** db-wal-recovery: step 1 ("Fix the WAL file so SQLite can read it") is never checked

**What the instruction requires**
> 1. Fix the WAL file so SQLite can read it
> 2. Extract ALL data from the database (including WAL changes)
> 3. Create a JSON file in /app/recovered.json

**What passes today**
`near-4-symptom/solve.sh` decrypts a scratch copy, writes the correct `recovered.json`, and leaves `/app/main.db-wal` encrypted, so SQLite on `/app/main.db` still sees 5 records. It passes.

**Why the tests miss it**
All tests read `/app/recovered.json`; none opens `/app/main.db`.

**Suggested fix** (`test_fix_addition.py`): open `/app/main.db` read-only with `sqlite3` and require 11 rows in `items`.
Checked locally: the reference solution passes; near-4 fails with "SQLite still sees 5 records".

---

## modernize-scientific-stack

**Title:** modernize-scientific-stack: the "DO NOT MODIFY" script and the version-constraint requirement are never checked

**What the instruction requires**
> - `/app/climate_analyzer/analyze_climate.py` - Original Python 2 script (DO NOT MODIFY)

> - Include numpy, pandas, and at least one of: matplotlib, scipy
> - Specify version constraints using >=, ==, or ~=

**What passes today**
- `near-1-partial/solve.sh` writes `requirements.txt` with bare `numpy`, `pandas`, `matplotlib` (no constraints). It passes.
- `near-4-over-broad/solve.sh` inserts a line into `/app/climate_analyzer/analyze_climate.py`. It passes.

**Why the tests miss it**
`test_dependency_file_exists` only checks that a dependency file exists; nothing checks its contents or the legacy script.

**Suggested fix** (`test_fix_addition.py`): require a version specifier for numpy and pandas and the presence of matplotlib or scipy; compare the legacy script's SHA-256 with the shipped file (`112e2626…65dd0`).
Checked locally: the reference solution passes; near-1 fails the first new test and near-4 the second.

---

## cobol-modernization

**Title:** cobol-modernization: every graded transaction is a valid sale, so a port that skips the COBOL validation passes

**What the instruction requires**
> create a new Python script located at /app/program.py, which performs the exact same operations as the COBOL program.

`program.cbl` only processes a sale when buyer, seller and book exist and the seller owns the book (`IF BOOK-OWNER = WS-SELLER-ID`, lines 76–77 and 112).

**What passes today**
`near-2-edge-case/solve.sh` is a port without the ownership check: it transfers money and the book even when the seller doesn't own it. It passes.

**Why the tests miss it**
`test_program_output` resets the data so that `B003` belongs to `U003`, then runs three sales that are all valid at the time they run. The rejection path is never exercised.

**Suggested fix** (`test_fix_addition.py`): from the same initial state, run `U002U001B0030000000010` (U001 doesn't own B003) and require all three .DAT files unchanged. That is GnuCOBOL 3.1's behavior for `program.cbl`; we checked that the same build reproduces the existing test's expected files.
Checked locally: the reference `program.py` passes; near-2 fails.

---

## sparql-university

**Title:** sparql-university: the graph can't distinguish "GB counted as EU" or ">= 10" from correct queries

**What the instruction requires**
> assume that "European Union countries" refers to the official EU member states as of 2025-08-16

> at least one has more than 10 students currently enrolled

**What passes today**
- `near-1-edge-case/solve.sh`: the reference query with `"GB"` added to the EU list (the UK left in 2020). It passes.
- `near-2-edge-case/solve.sh`: the reference query with `HAVING(COUNT(DISTINCT ?student) >= 10)`. It passes.

**Why the tests miss it**
The graph contains no `"GB"` literal and no department with exactly 10 current students, so both queries return the same rows as the reference.

**Suggested fix** (`test_fix_addition.py`): two extra tests that run the agent's query on modified copies of the graph: NKUA moved to `GB`, and HistoryAndPhilosophy_NKUA reduced from 12 to exactly 10 current students. In both, Aristotle Tympas must drop out. The expected rows come from the reference query.
Checked locally with rdflib: the reference passes both; near-1 fails the GB test and near-2 the 10-student test.

---

## prove-plus-comm

**Title:** prove-plus-comm: an `Axiom` stating the theorem, or `Admitted.` with `Qed.` in a comment, passes as a proof

**What the instruction requires**
> Add the missing steps to complete the proof ... The proof should be completed using Coq's tactics

**What passes today**
- `axiom-proof/solve.sh` declares `Axiom plus_comm_axiom : forall n m : nat, n + m = m + n.` and proves the theorem with `apply plus_comm_axiom.` It passes.
- `admitted-in-comment/solve.sh` ends the proof with `Admitted. (* Qed. *)`. It passes: the `"admit" not in content` check is case-sensitive, and `"Qed." in content` matches the comment.

**Why the tests miss it**
The tests check strings in `plus_comm.v` and that it compiles; nothing asks Coq whether the proof depends on axioms.

**Suggested fix** (`test_fix_addition.py`): compile a two-line file `Require Import plus_comm. Print Assumptions plus_comm.` and require `Closed under the global context`.
Checked locally with Coq 8.18: the reference passes; both solutions above fail.

