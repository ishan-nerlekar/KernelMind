"""Hidden verifier for vlan-state-report (ported from KernelMind v1 vlan-state v2 grade.py).

Each structured case is checked twice in fresh processes:
  cli    - `python3 candidate.py` with the JSON on stdin; output must equal the expected JSON
  handle - import candidate, call handle(request); response must match AND the request object
           must be left unmodified (the contract forbids mutating the input)
Raw cases send malformed bytes to the CLI only.
Expected outputs are written out explicitly in the fixture files; no reference code is used.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

APP = Path(os.environ.get("APP_DIR", "/app"))
LOGS = Path(os.environ.get("LOGS_DIR", "/logs/verifier"))
HERE = Path(__file__).parent

HANDLE_PROBE = r"""
import copy, json, sys
sys.path.insert(0, '.')
from candidate import handle
request = json.loads(sys.stdin.read())
before = copy.deepcopy(request)
response = handle(request)
print(json.dumps({'response': response, 'input_unchanged': request == before
                  and json.dumps(request, sort_keys=True) == json.dumps(before, sort_keys=True)}))
"""


def canonical(value):
    # sort_keys + allow_nan=False keeps true/1 and false/0 distinct and rejects NaN.
    try:
        return json.dumps(value, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        return None


def run(argv, stdin):
    try:
        p = subprocess.run(argv, cwd=APP, input=stdin, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    if p.returncode != 0:
        return None, f"exit {p.returncode}: {p.stderr[-300:]}"
    try:
        return json.loads(p.stdout), None
    except json.JSONDecodeError:
        return None, "stdout is not one JSON value"


def main():
    cases = json.loads((HERE / "cases.json").read_text()) + json.loads((HERE / "raw-cases.json").read_text())
    failures, total = [], 0
    for case in cases:
        if "raw_stdin" in case:
            checks = [("cli", [sys.executable, "candidate.py"], case["raw_stdin"], case["expected"])]
        else:
            stdin = json.dumps(case["input"])
            checks = [("cli", [sys.executable, "candidate.py"], stdin, case["expected"]),
                      ("handle", [sys.executable, "-c", HANDLE_PROBE], stdin,
                       {"response": case["expected"], "input_unchanged": True})]
        for label, argv, stdin, expected in checks:
            total += 1
            actual, error = run(argv, stdin)
            if error:
                failures.append({"case": case["id"], "check": label, "name": "candidate_execution", "detail": error})
            elif canonical(actual) != canonical(expected):
                mutated = label == "handle" and isinstance(actual, dict) and actual.get("input_unchanged") is False
                failures.append({"case": case["id"], "check": label,
                                 "name": "input_mutation" if mutated else case["category"],
                                 "expected": expected, "actual": actual})
    summary = {"checks_total": total, "checks_passed": total - len(failures),
               "failed_checks": sorted({f["name"] for f in failures}), "failures": failures[:40]}
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / "results.json").write_text(json.dumps(summary, indent=2))
    print(f"{summary['checks_passed']}/{total} passed; failed checks: {summary['failed_checks']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
