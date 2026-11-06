"""Apply fixes and run a task's hidden verifier inside an environment."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from .env import Environment
from .task import Fix


@dataclass
class Verdict:
    passed: bool
    failed_checks: list[str] = field(default_factory=list)
    checks_total: int | None = None
    checks_passed: int | None = None
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def apply_fix(env: Environment, fix: Fix, timeout: int = 300) -> None:
    env.copy_in(fix.path, "/solution")
    r = env.exec('bash "$SOLUTION_DIR/solve.sh"', timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"{fix.kind} '{fix.name}' solve.sh failed:\n{r.output[-2000:]}")
    env.exec('rm -rf "$SOLUTION_DIR"/*')


def run_tests(env: Environment) -> Verdict:
    """Copy the hidden tests in and run them. Reward 1 means pass; anything else is a fail."""
    task = env.task
    env.copy_in(task.root / "tests", "/tests")
    r = env.exec('mkdir -p "$LOGS_DIR" && bash "$TESTS_DIR/test.sh"', timeout=task.limits["test_timeout_sec"])
    reward = (env.read_text("/logs/verifier/reward.txt") or "").strip()
    details = {}
    raw = env.read_text("/logs/verifier/results.json")
    if raw:
        try:
            details = json.loads(raw)
        except json.JSONDecodeError:
            pass
    if not details and (ctrf := env.read_text("/logs/verifier/ctrf.json")):  # Terminal-Bench / Harbor tests
        try:
            tests = json.loads(ctrf)["results"]["tests"]
            details = {"failed_checks": [t["name"] for t in tests if t.get("status") != "passed"],
                       "checks_total": len(tests), "checks_passed": sum(t.get("status") == "passed" for t in tests)}
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    note = "timed out" if r.timed_out else ("" if reward else "verifier wrote no reward: " + r.output[-500:])
    return Verdict(passed=reward == "1", failed_checks=sorted(set(details.get("failed_checks", []))),
                   checks_total=details.get("checks_total"), checks_passed=details.get("checks_passed"),
                   note=note)
