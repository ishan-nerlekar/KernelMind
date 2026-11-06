def test_secret_absent_from_every_object():
    """The secret must not survive anywhere in the object store: reachable, reflog-reachable,
    unreachable or packed. `git fsck --lost-found` only lists dangling *tips*, so a blob inside a
    dangling commit, or anything the reflog still references, is not covered by the check above."""
    result = subprocess.run(
        ["git", "-C", "/app/repo", "cat-file", "--batch-all-objects", "--batch"],
        capture_output=True,
    )
    assert result.returncode == 0, f"git cat-file failed: {result.stderr}"
    assert b"secret[" not in result.stdout, "Found 'secret[' in an object still stored in the repo"


def test_commit_messages_unchanged():
    """Instruction: 'make sure irrelevant files and commit messages remain untouched'."""
    result = subprocess.run(
        ["git", "-C", "/app/repo", "log", "--all", "--format=%B"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Git log command failed: {result.stderr}"
    messages = [m.strip() for m in result.stdout.split("\n\n") if m.strip()]
    assert messages and all(m == "chore: init e665d1a2-04a7-4e61-b523-e897e231d9cc" for m in messages), messages
