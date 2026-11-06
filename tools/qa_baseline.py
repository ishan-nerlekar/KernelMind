"""Baseline: how many of the known Terminal-Bench verifier gaps does a QA reviewer find by reading the tests?

A reviewer model sees what a human or QA agent reviewing a task would: the instruction, the hidden tests, the
environment files and the reference solution. It lists ways a wrong solution could pass, each with a script.
Unlike the auditor, it reads the tests and executes nothing.

    python3 tools/qa_baseline.py review --model claude-opus-5-5 --max-cost 5     # resumable
    python3 tools/qa_baseline.py sheet  --model claude-opus-5-5                  # results/qa-<model>/review.md
    # judge the sheet by hand into audit/qa/judged-<model>.json, then:
    python3 tools/qa_baseline.py score  --model claude-opus-5-5
    python3 tools/qa_baseline.py grade  --model claude-opus-5-5                  # optional: run its scripts

Ground truth: audit/qa/known_gaps.json (14 gaps behind issues #92-#99). The reviewer models' training data
predates those issues (filed Nov 7, 2026).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from kernelmind.audit import audit_task, complete  # noqa: E402
from kernelmind.task import load_tasks  # noqa: E402

# The 26 Terminal-Bench 2.0 tasks the auditor graded (docs/AUDIT.md: pilot + T5).
TASKS = """cancel-async-tasks large-scale-text-editing regex-log sqlite-db-truncate cobol-modernization code-from-image
configure-git-webserver constraints-scheduling db-wal-recovery fix-git git-leak-recovery headless-terminal
log-summary-date-ranges merge-diff-arc-agi-task modernize-scientific-stack openssl-selfsigned-cert overfull-hbox
password-recovery polyglot-c-py polyglot-rust-c prove-plus-comm raman-fitting sanitize-git-repo sparql-university
torch-pipeline-parallelism torch-tensor-parallelism""".split()
KNOWN = REPO / "audit" / "qa" / "known_gaps.json"
MAX_GAPS = 6

PROMPT = """You are a QA reviewer for an AI agent benchmark. An agent receives the INSTRUCTION below and works in a \
Linux container. When it finishes, the TESTS below are copied in and run against the final container state; \
the task passes if they pass. The environment files and the reference solution are included for context.

Find ways a solution could PASS these tests while NOT satisfying the instruction: requirements the tests never \
check, cases the test inputs don't cover, checks that can be satisfied without doing the task. Only report a gap \
when the instruction is explicit about the requirement. For each gap, give a concrete wrong solution as a bash \
script that the tests would accept (it runs in the container's working directory, like the reference).

Report at most {k} gaps, most serious first. If the tests look sound, return an empty list.
Reply with JSON only:
{{"gaps": [{{"requirement": "<the instruction's words>", "wrong_solution": "<what it does wrong>",
  "why_tests_pass": "<which check misses it and why>", "severity": "high|medium|low", "solve_sh": "#!/bin/bash ..."}}]}}

=== INSTRUCTION ===
{instruction}

=== TESTS ===
{tests}

=== ENVIRONMENT FILES ===
{env}

=== REFERENCE SOLUTION ===
{reference}
"""


def _files(root: Path, per_file: int, total: int) -> str:
    out, used = [], 0
    for f in sorted(p for p in root.rglob("*") if p.is_file()) if root.exists() else []:
        try:
            text = f.read_text()
        except (UnicodeDecodeError, OSError):
            out.append(f"--- {f.relative_to(root)} (binary, {f.stat().st_size} bytes)")
            continue
        if len(text) > per_file:
            text = text[:per_file] + f"\n[... truncated, {len(text)} chars total]"
        if used + len(text) > total:
            out.append(f"--- {f.relative_to(root)} (omitted: input budget)")
            continue
        used += len(text)
        out.append(f"--- {f.relative_to(root)}\n{text}")
    return "\n".join(out) or "(none)"


def slug(model: str) -> str:
    return re.sub(r"[^a-z0-9.-]+", "-", model.lower())


def cmd_review(a) -> None:
    out = REPO / "results" / f"qa-{slug(a.model)}"
    out.mkdir(parents=True, exist_ok=True)
    spent, failures = 0.0, 0
    for task in load_tasks(TASKS, None, Path(a.tasks_dir).expanduser().resolve()):
        f = out / f"{task.id}.json"
        if f.exists():
            continue
        if spent >= a.max_cost:
            print("stopping at --max-cost; rerun to resume")
            break
        prompt = PROMPT.format(k=MAX_GAPS, instruction=task.instruction[:8000],
                               tests=_files(task.root / "tests", 20000, 40000),
                               env=_files(task.root / "environment", 6000, 20000),
                               reference=(task.root / "solution" / "solve.sh").read_text()[:15000])
        print(f"reviewing {task.id} ...", flush=True)
        try:
            gen, cost = complete(a.model, prompt, 16000)
        except Exception as e:
            print(f"  failed: {str(e)[:300]}")
            failures += 1
            if failures == 3:  # out of credits, bad key, outage: don't burn through every task
                print("stopping after 3 failures in a row; rerun to resume")
                break
            continue
        failures, spent = 0, spent + cost
        gaps = gen.get("gaps", [])[:MAX_GAPS]
        f.write_text(json.dumps({"task": task.id, "model": a.model, "cost": cost, "gaps": gaps}, indent=1))
        print(f"  {len(gaps)} gaps flagged; ${cost:.3f}")
    print(f"spent ${spent:.2f}")


def _load(model: str) -> dict[str, dict]:
    out = REPO / "results" / f"qa-{slug(model)}"
    return {f.stem: json.loads(f.read_text()) for f in sorted(out.glob("*.json")) if f.stem in TASKS}


def cmd_sheet(a) -> None:
    known, res = json.loads(KNOWN.read_text()), _load(a.model)
    lines = [f"# QA reviewer flags: {a.model}", "",
             f"Tasks reviewed: {len(res)}/{len(TASKS)}; flags: {sum(len(r['gaps']) for r in res.values())}; "
             f"cost ${sum(r['cost'] for r in res.values()):.2f}", ""]
    for t in TASKS:
        if t not in res:
            continue
        lines.append(f"## {t}")
        for g in known.get(t, []):
            lines.append(f"- KNOWN `{g['id']}`: {g['gap']}")
        for i, g in enumerate(res[t]["gaps"], 1):
            lines += [f"{i}. [{g.get('severity', '?')}] **{g.get('requirement', '')}**",
                      f"   - wrong: {g.get('wrong_solution', '')}", f"   - why: {g.get('why_tests_pass', '')}"]
        lines.append("")
    p = REPO / "results" / f"qa-{slug(a.model)}" / "review.md"
    p.write_text("\n".join(lines))
    print(p)


def cmd_score(a) -> None:
    """judged-<model>.json: {"<task>": {"<known gap id>": <matching flag number or null>, ...}, ...}"""
    known, res = json.loads(KNOWN.read_text()), _load(a.model)
    judged = json.loads((REPO / "audit" / "qa" / f"judged-{slug(a.model)}.json").read_text())
    total = found = 0
    for t, gaps in known.items():
        if t.startswith("_"):
            continue
        for g in gaps:
            total += 1
            hit = judged.get(t, {}).get(g["id"])
            found += hit is not None
            print(f"{t:28} {g['id']:18} {'flag ' + str(hit) if hit is not None else 'missed'}")
    flags = sum(len(r["gaps"]) for r in res.values())
    print(f"\nrecall on known gaps: {found}/{total}; flags raised: {flags} across {len(res)} tasks")


def cmd_grade(a) -> None:
    """Run each flag's script against the task's own tests: a flag whose script passes is a lenient suspect."""
    res, out = _load(a.model), REPO / "results" / f"qa-{slug(a.model)}" / "graded"
    out.mkdir(parents=True, exist_ok=True)
    root = Path(a.tasks_dir).expanduser().resolve()
    for task in load_tasks([t for t in TASKS if res.get(t, {}).get("gaps")], None, root):
        if (out / f"{task.id}.json").exists():
            continue
        print(f"grading {task.id} ...", flush=True)
        given = {"near_misses": [{"violates": g.get("requirement", ""), "solve_sh": g.get("solve_sh", "")}
                                 for g in res[task.id]["gaps"]]}
        r, _ = audit_task(task, out, a.backend, None, 0, 0, 0, given=given)
        print(f"  passed tests: {[c['candidate'] for c in r['candidates'] if c['outcome'] == 'lenient-suspect']}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["review", "sheet", "score", "grade"])
    p.add_argument("--model", required=True)
    p.add_argument("--max-cost", type=float, default=5.0)
    p.add_argument("--tasks-dir", default=str(REPO / "external" / "tb2"))
    p.add_argument("--backend", default="docker")
    a = p.parse_args()
    {"review": cmd_review, "sheet": cmd_sheet, "score": cmd_score, "grade": cmd_grade}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
