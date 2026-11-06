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
