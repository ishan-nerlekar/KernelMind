"""Make copies of KernelMind tasks with one known grader flaw each, for measuring the auditor (T4).

For each task, the tests that its first wrong-fix control is pinned to (controls/<first>/expect.txt)
are disabled in tests/visible and tests/hidden. That control is the *witness*: it must pass the
weakened grader. Output: audit/planted-kernelmind/<task>/ plus planted.json describing each flaw.

    python3 tools/plant_flaws.py [--also validate.json] lease-renew-gateway peer-timeout-flap ...
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "audit" / "planted-kernelmind"


def plant(task_id: str, also: list[str]) -> dict:
    src = REPO / "tasks" / task_id
    first = sorted((src / "controls").iterdir())[0]
    removed = [l.strip() for l in (first / "expect.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]
    removed += [n for n in also if n not in removed]
    dst = OUT / task_id
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("alternatives"))
    toml = dst / "task.toml"  # audited like an external task: no KernelMind structure rules
    toml.write_text("external = true\n" + toml.read_text())
    for c in (dst / "controls").iterdir():  # keep only the witness control
        if c.name != first.name:
            shutil.rmtree(c)
    stripped = []
    for f in sorted((dst / "tests").rglob("*_test.go")):
        text = f.read_text()
        names = [n for n in removed if re.search(rf"^func {n}\(", text, re.M)]
        for n in names:  # renamed, not deleted: go test stops running it, but its imports stay used
            text = re.sub(rf"^func {n}\(", f"func disabled{n}(", text, flags=re.M)
        if names:
            f.write_text(text)
            stripped += [f"{f.relative_to(dst)}:{n}" for n in names]
    missing = [n for n in removed if not any(s.endswith(":" + n) for s in stripped)]
    if missing:
        raise SystemExit(f"{task_id}: tests not found: {missing}")
    return {"task": task_id, "witness": first.name, "removed_tests": removed, "stripped": stripped}


def main(ids: list[str]) -> int:
    """--also FILE: a `kernelmind validate --json` report of an earlier planting; any check the witness
    still failed there is disabled too, so the witness passes the weakened grader."""
    also: dict[str, list[str]] = {}
    if ids[:1] == ["--also"]:
        for r in json.loads(Path(ids[1]).read_text()):
            if r["kind"] == "control" and r["verdict"]:
                also[r["task"]] = r["verdict"]["failed_checks"]
        ids = ids[2:]
    OUT.mkdir(parents=True, exist_ok=True)
    flaws = [plant(i, also.get(i, [])) for i in ids]
    (OUT / "planted.json").write_text(json.dumps(flaws, indent=1) + "\n")
    for f in flaws:
        print(f"{f['task']}: removed {', '.join(f['removed_tests'])} (witness {f['witness']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
