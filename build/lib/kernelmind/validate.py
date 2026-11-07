"""Validate tasks: the starter must fail, every valid fix must pass, every wrong fix must fail.

This is the same idea as SWE-bench Verified's human validation, automated: a task is only
trustworthy if its tests can tell a correct fix from plausible incorrect ones.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .env import make_env
from .task import Fix, Task
from .verify import Verdict, apply_fix, run_tests


@dataclass
class Check:
    task: str
    subject: str  # "starter" or the fix name
    kind: str
    expected: str  # "pass" | "fail"
    verdict: Verdict | None
    ok: bool
    reason: str
    seconds: float


def _evaluate(task: Task, backend: str, fix: Fix | None) -> Verdict:
    with make_env(task, backend) as env:
        if fix:
            apply_fix(env, fix)
        return run_tests(env)


def validate_task(task: Task, backend: str) -> list[Check]:
    problems = task.problems()
    if problems:
        return [Check(task.id, "structure", "structure", "valid", None, False, "; ".join(problems), 0)]
    subjects: list[tuple[str, str, Fix | None, bool]] = [("starter", "starter", None, False)]
    subjects += [(f.name, f.kind, f, f.should_pass) for f in task.fixes()]
    checks = []
    for name, kind, fix, should_pass in subjects:
        start = time.time()
        try:
            v = _evaluate(task, backend, fix)
        except Exception as e:  # infrastructure problem, never counted as a task result
            checks.append(Check(task.id, name, kind, "pass" if should_pass else "fail", None, False,
                                f"error: {e}", time.time() - start))
            continue
        if should_pass:
            ok, reason = v.passed, ("" if v.passed else f"failed {v.failed_checks[:5]} {v.note}")
        elif v.passed:
            ok, reason = False, "wrong fix PASSED: tests cannot tell it apart from a correct fix"
        else:
            expected = fix.expect_failures if fix else task.meta.get("starter_fails_on", [])
            missing = [c for c in expected if c not in v.failed_checks]
            ok = not missing
            reason = f"did not fail on expected check(s) {missing}; failed {v.failed_checks[:5]}" if missing else ""
        checks.append(Check(task.id, name, kind, "pass" if should_pass else "fail", v, ok, reason,
                            time.time() - start))
    return checks
