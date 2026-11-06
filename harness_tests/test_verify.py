import json
from pathlib import Path

from kernelmind.env import ExecResult
from kernelmind.task import Task
from kernelmind.verify import run_tests


class FakeEnv:
    def __init__(self, files):
        self.task = Task(Path("."), {"id": "t", "limits": {}})
        self.files = files

    def copy_in(self, src, dst):
        pass

    def exec(self, command, timeout=120):
        return ExecResult(0, "", False)

    def read_text(self, path):
        return self.files.get(path)


def test_ctrf_failures_reported():
    ctrf = {"results": {"tests": [{"name": "test_a", "status": "passed"}, {"name": "test_b", "status": "failed"}]}}
    v = run_tests(FakeEnv({"/logs/verifier/reward.txt": "0", "/logs/verifier/ctrf.json": json.dumps(ctrf)}))
    assert not v.passed and v.failed_checks == ["test_b"] and (v.checks_total, v.checks_passed) == (2, 1)


def test_results_json_preferred():
    res = {"failed_checks": ["X"], "checks_total": 3, "checks_passed": 2}
    v = run_tests(FakeEnv({"/logs/verifier/reward.txt": "0", "/logs/verifier/results.json": json.dumps(res),
                           "/logs/verifier/ctrf.json": "{}"}))
    assert v.failed_checks == ["X"]
