#!/usr/bin/env python3
"""Generate Go tasks from the clean apnet substrate plus a small spec per task.

    python3 tools/taskgen.py            # build every taskgen/<id>/ into tasks/<id>/
    python3 tools/taskgen.py lease-...  # build selected tasks

A spec (taskgen/<id>/spec.toml) holds the metadata, the bug as exact text edits to the clean
substrate, and wrong fixes (controls) / alternative fixes as edits to the buggy starter.
taskgen/<id>/instruction.md is the symptom report. taskgen/<id>/hidden/ holds hidden test files at
their module paths.

Checks before writing anything: every edit matches exactly once, the substrate's own (visible)
tests pass on the clean code AND on the starter (so running `go test` doesn't reveal the bug),
and the hidden tests compile against the starter.
"""
from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SUBSTRATES = {"apnet": REPO / "substrate" / "apnet", "gobgp": REPO / "substrate" / "gobgp"}
# Packages graded for each substrate. GoBGP's pkg/server, pkg/config and pkg/metrics tests open real
# listeners on [::] and need IPv6, so they are left out of grading for portability.
DEFAULT_PACKAGES = {"apnet": "./...",
                    "gobgp": "./internal/pkg/table/... ./pkg/packet/... ./pkg/apiutil/... ./pkg/zebra/... ./cmd/gobgp/... ./pkg/config/oc/..."}
SPECS = REPO / "taskgen"
TASKS = REPO / "tasks"
META_KEYS = ("id", "tier", "root_cause", "origin", "language", "substrate", "summary", "inspired_by",
             "starter_fails_on", "limits", "docker")

DOCKERFILE = """ARG BASE_IMAGE=golang:1.24-bookworm
FROM ${{BASE_IMAGE}}
ENV GOTOOLCHAIN=local GOFLAGS=-mod=mod CGO_ENABLED=1
WORKDIR /app
{download}COPY app/ /app/
# Warm the build cache so neither the agent nor the verifier pays for a cold compile.
RUN go build ./... && go test -count=1 {flags} -run '^$' {packages} > /dev/null
# A single baseline commit lets the harness record the agent's diff. No project history is included.
RUN git init -q && git add -A && git -c user.email=kernelmind@local -c user.name=kernelmind commit -qm baseline
"""

TEST_SH = r"""#!/usr/bin/env bash
# Hidden verifier: restores the project's original tests, adds the hidden ones, runs everything.
# Agent edits to test files do not count. Reward 1 only if every test passes.
set -uo pipefail
APP="${{APP_DIR:-/app}}"; T="${{TESTS_DIR:-/tests}}"; LOGS="${{LOGS_DIR:-/logs/verifier}}"
mkdir -p "$LOGS"; cd "$APP" || exit 1
export GOTOOLCHAIN=local GOFLAGS=-mod=mod
find . -name '*_test.go' -not -path './.git/*' -delete
cp -r "$T/visible/." "$APP/"
cp -r "$T/hidden/." "$APP/"
timeout 600 go test -count=1 -timeout 180s {flags} -v {packages} > "$LOGS/go-test.log" 2>&1
status=$?
{extra}
failed=$(grep -oE '^[[:space:]]*--- FAIL: [A-Za-z0-9_]+' "$LOGS/go-test.log" | awk '{{print $3}}' | sort -u | tr '\n' ' ')
grep -qE '\[(build|setup) failed\]' "$LOGS/go-test.log" && failed="$failed build_failed"
grep -q 'panic: test timed out' "$LOGS/go-test.log" && failed="$failed test_timeout"
[ "$status" -eq 124 ] && failed="$failed verifier_timeout"
[ "$status" -ne 0 ] && [ -z "${{failed// /}}" ] && failed="test_binary_failed"
total=$(grep -cE '^[[:space:]]*--- (PASS|FAIL): ' "$LOGS/go-test.log")
passed=$(grep -cE '^[[:space:]]*--- PASS: ' "$LOGS/go-test.log")
list=$(for f in $failed; do printf '"%s",' "$f"; done); list="[${{list%,}}]"
printf '{{"checks_total": %s, "checks_passed": %s, "failed_checks": %s}}\n' "$total" "$passed" "$list" > "$LOGS/results.json"
if [ "$status" -eq 0 ]; then echo 1 > "$LOGS/reward.txt"; else echo 0 > "$LOGS/reward.txt"; fi
grep -E '^(ok|FAIL|---)' "$LOGS/go-test.log" | grep -v -- '--- PASS' | tail -n 20
"""

SOLVE_SH = """#!/usr/bin/env bash
# Apply this fix to the workspace.
set -euo pipefail
cd "${APP_DIR:-/app}"
git apply --whitespace=nowarn "$(dirname "$0")/fix.patch"
"""


def apply_edits(root: Path, edits: list[dict], where: str) -> None:
    for e in edits:
        p = root / e["file"]
        text = p.read_text()
        n = text.count(e["old"])
        if n != 1:
            raise SystemExit(f"{where}: edit to {e['file']} matches {n} times (must be exactly 1):\n{e['old']}")
        p.write_text(text.replace(e["old"], e["new"]))


def unified_patch(a_root: Path, b_root: Path, files: list[str]) -> str:
    out = []
    for f in sorted(set(files)):
        a = (a_root / f).read_text().splitlines(keepends=True)
        b = (b_root / f).read_text().splitlines(keepends=True)
        out.extend(difflib.unified_diff(a, b, f"a/{f}", f"b/{f}"))
    return "".join(out)


def go_test(root: Path, flags: str, what: str, packages: str = "./...", extra: list[str] = ()) -> None:
    env = {**os.environ, "GOFLAGS": "-mod=mod", "GOTOOLCHAIN": "local"}
    cmd = f"go build ./... && go test -count=1 {flags} {packages}" + "".join(f" && go test -count=1 {flags} {r}" for r in extra)
    r = subprocess.run(cmd, shell=True, cwd=root,
                       capture_output=True, text=True, env=env)
    if r.returncode:
        raise SystemExit(f"{what} failed:\n{(r.stdout + r.stderr)[-3000:]}")


def copy_tests(src: Path, dst: Path) -> None:
    for t in src.rglob("*_test.go"):
        target = dst / t.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(t, target)


def write_fix(dir_: Path, patch: str, expect: list[str] | None = None, comment: str = "") -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / "fix.patch").write_text(patch)
    (dir_ / "solve.sh").write_text(SOLVE_SH)
    os.chmod(dir_ / "solve.sh", 0o755)
    if expect is not None:
        (dir_ / "expect.txt").write_text(f"# {comment}\n" + "".join(f"{c}\n" for c in expect))


def build(task_id: str) -> None:
    spec_dir = SPECS / task_id
    spec = tomllib.loads((spec_dir / "spec.toml").read_text())
    if spec["id"] != task_id:
        raise SystemExit(f"{task_id}: spec id is {spec['id']}")
    flags = spec.get("go_test_flags", "")
    substrate = spec.get("substrate", "apnet")
    packages = spec.get("test_packages", DEFAULT_PACKAGES[substrate])
    src = SUBSTRATES[substrate]
    with tempfile.TemporaryDirectory() as tmp:
        clean, starter = Path(tmp, "clean"), Path(tmp, "starter")
        shutil.copytree(src, clean)
        shutil.copytree(src, starter)
        # Transplanted features: new code (taskgen/<id>/feature/ files plus [[feature]] edits)
        # added to both trees. The bug is then planted only in the starter.
        for tree in (clean, starter):
            if (spec_dir / "feature").is_dir():
                shutil.copytree(spec_dir / "feature", tree, dirs_exist_ok=True)
            apply_edits(tree, spec.get("feature", []), f"{task_id} feature")
        apply_edits(starter, spec["bug"], f"{task_id} bug")
        # Evidence the engineer would have (captures, logs, RIB dumps) ships inside the workspace.
        if (spec_dir / "app_files").is_dir():
            shutil.copytree(spec_dir / "app_files", starter, dirs_exist_ok=True)
        # Existing tests that would reveal the bug are removed from the agent's copy; the originals
        # still run at grading time (tests/visible is copied from the clean tree).
        for h in spec.get("hide", []):
            r = subprocess.run(["go", "run", ".", str(starter / h["file"]), *h["tests"]], cwd=REPO / "tools" / "stripfuncs",
                               capture_output=True, text=True, env={**os.environ, "GOFLAGS": ""})
            if r.returncode:
                raise SystemExit(f"{task_id}: hiding tests in {h['file']}: {r.stderr}")
        go_test(clean, flags, f"{task_id}: visible tests on the clean tree", packages, spec.get("extra_runs", []))
        go_test(starter, flags, f"{task_id}: visible tests on the starter (the bug must not be visible)", packages, spec.get("extra_runs", []))
        hidden = spec_dir / "hidden"
        probe = Path(tmp, "probe")
        shutil.copytree(starter, probe)
        shutil.copytree(hidden, probe, dirs_exist_ok=True)
        r = subprocess.run(f"go test -count=1 -run '^$' {packages}", shell=True, cwd=probe, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"{task_id}: hidden tests do not compile against the starter:\n{r.stderr[-2000:]}")

        out = TASKS / task_id
        if out.exists():
            shutil.rmtree(out)
        (out / "environment").mkdir(parents=True)
        shutil.copytree(starter, out / "environment" / "app")
        download = "COPY app/go.mod app/go.sum /app/\nRUN go mod download\n" if (src / "go.sum").exists() else ""
        (out / "environment" / "Dockerfile").write_text(DOCKERFILE.format(flags=flags, packages=packages, download=download))
        meta = {k: spec[k] for k in META_KEYS if k in spec}
        (out / "task.toml").write_text(to_toml(meta))
        shutil.copy2(spec_dir / "instruction.md", out / "instruction.md")

        tests = out / "tests"
        copy_tests(clean, tests / "visible")
        shutil.copytree(hidden, tests / "hidden")
        extra = "".join(f'timeout 300 go test -count=1 -timeout 120s {flags} -v {run} >> "$LOGS/go-test.log" 2>&1 || status=$?\n'
                        for run in spec.get("extra_runs", []))
        (tests / "test.sh").write_text(TEST_SH.format(flags=flags, packages=packages, extra=extra))
        os.chmod(tests / "test.sh", 0o755)

        bug_files = [e["file"] for e in spec["bug"]]
        write_fix(out / "solution", unified_patch(starter, clean, bug_files))
        for alt in spec.get("alternative", []):
            fixed = Path(tmp, "alt-" + alt["name"])
            shutil.copytree(starter, fixed)
            apply_edits(fixed, alt["edit"], f"{task_id} alternative {alt['name']}")
            write_fix(out / "alternatives" / alt["name"], unified_patch(starter, fixed, [e["file"] for e in alt["edit"]]))
        for ctl in spec.get("control", []):
            wrong = Path(tmp, "ctl-" + ctl["name"])
            shutil.copytree(starter, wrong)
            apply_edits(wrong, ctl["edit"], f"{task_id} control {ctl['name']}")
            write_fix(out / "controls" / ctl["name"], unified_patch(starter, wrong, [e["file"] for e in ctl["edit"]]),
                      ctl["expect"], ctl.get("comment", ""))
    print(f"built {task_id}")


def to_toml(meta: dict) -> str:
    def val(v):
        if isinstance(v, str):
            return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, list):
            return "[" + ", ".join(val(x) for x in v) + "]"
        return str(v)
    lines, tables = [], []
    for k, v in meta.items():
        (tables if isinstance(v, dict) else lines).append((k, v))
    out = ["# Generated by tools/taskgen.py from taskgen/; edit the spec, not this file."]
    out += [f"{k} = {val(v)}" for k, v in lines]
    for k, v in tables:
        out += ["", f"[{k}]"] + [f"{kk} = {val(vv)}" for kk, vv in v.items()]
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ids = argv or sorted(p.name for p in SPECS.iterdir() if (p / "spec.toml").exists())
    for i in ids:
        build(i)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
