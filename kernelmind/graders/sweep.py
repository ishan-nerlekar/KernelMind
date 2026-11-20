"""Sweep a whole framework: audit every grader it defines, rank by findings.

No datasets are downloaded, so each grader is audited on synthetic samples: the first
target kind whose answers the grader reads (a letter with options, a number, a word).
Graders that read none of them are reported as such, not guessed at.

lm-eval tasks that share a filter pipeline and metric are graded identically, so each
distinct configuration is audited once and its result attributed to every task using it.
Inspect tasks are built one per subprocess (some evals import heavy dependencies or
touch sandboxes at build time), with a timeout.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict

from .core import Result, Sample, audit, findings

CANDIDATES = [
    Sample("C", choices=["first option", "second option", "third option", "fourth option"]),
    Sample("C", choices=[f"option {i}" for i in range(10)]),
    Sample("18"),
    Sample("yes"),
    Sample("Paris"),
]


async def audit_any_target(g) -> list[Result]:
    last: list[Result] = []
    for s in CANDIDATES:
        try:
            res = await audit(g, s)
        except Exception as e:  # noqa: BLE001
            return [Result(g.name, s.id, "setup", "", f"(error: {type(e).__name__}: {e})"[:200], "", "", "ERROR", "")]
        if not any(r.outcome == "NOFORMAT" for r in res):
            for r in res:
                r.sample = f"target={s.target}"
            return res
        last = res
    return last


# ------------------------------------------------------------------ lm-eval


_PASSTHROUGH = {"take_first", "take_first_k", "remove_whitespace", "lowercase", "uppercase", "map", "majority_vote"}


def extractive(pipeline: dict) -> bool:
    """True when the pipeline pulls an answer out of the output (a regex or custom filter),
    rather than comparing the whole output."""
    return any(str(f.get("function")) not in _PASSTHROUGH for f in pipeline.get("filter", []))


def lmeval_signatures(limit: int | None = None) -> dict[str, list[str]]:
    """{representative spec: [tasks with the same filter pipeline + metric config]}"""
    from .lmeval_adapter import _task_manager
    from lm_eval.tasks._yaml_loader import load_yaml

    groups: dict[str, list[str]] = defaultdict(list)
    for name, e in _task_manager().task_index.items():
        if "TASK" not in str(e.kind).upper() or not e.yaml_path:
            continue
        try:
            cfg = load_yaml(e.yaml_path, resolve_func=False)
        except Exception:  # noqa: BLE001
            continue
        if cfg.get("output_type") != "generate_until" or cfg.get("process_results"):
            continue
        for p in cfg.get("filter_list") or [{"name": "none", "filter": [{"function": "take_first"}]}]:
            if not extractive(p):
                continue  # the whole output is compared (QA, translation): strict by design
            key = json.dumps([p.get("filter"), cfg.get("metric_list")], sort_keys=True, default=str)
            groups[key].append(f"{name}@{p['name']}")
    reps = {members[0]: members for members in groups.values()}
    return dict(list(reps.items())[:limit]) if limit else reps


async def sweep_lmeval(limit: int | None = None) -> tuple[list[Result], dict[str, list[str]]]:
    from .lmeval_adapter import LmEvalGrader

    sigs = lmeval_signatures(limit)
    out: list[Result] = []
    for spec in sigs:
        try:
            g = LmEvalGrader(spec)
        except Exception as e:  # noqa: BLE001
            out.append(Result(f"lmeval:{spec}", "", "setup", "", f"(skipped: {e})"[:200], "", "", "SKIP", ""))
            continue
        out += await audit_any_target(g)
    return out, sigs


# ------------------------------------------------------------------ Inspect


def inspect_tasks(package: str = "inspect_evals") -> list[str]:
    from inspect_ai._util.registry import registry_find

    __import__(f"{package}._registry")
    names = sorted({i.name for i in (getattr(t, "__registry_info__", None) for t in
                                     registry_find(lambda i: i.type == "task")) if i and i.name.startswith(package)})
    return names


def _inspect_one(task: str) -> list[dict]:
    from .inspect_adapter import InspectGrader

    res = asyncio.run(audit_any_target(InspectGrader(task)))
    return [asdict(r) for r in res]


def sweep_inspect(tasks: list[str], timeout: int = 120, python: str = sys.executable) -> list[Result]:
    out: list[Result] = []
    for t in tasks:
        code = f"import json,sys; from kernelmind.graders.sweep import _inspect_one; print(json.dumps(_inspect_one({t!r})))"
        try:
            p = subprocess.run([python, "-c", code], capture_output=True, text=True, timeout=timeout)
            line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
            rows = json.loads(line) if line.startswith("[") else None
        except subprocess.TimeoutExpired:
            rows = None
            p = None
        if rows is None:
            why = "timeout" if p is None else (p.stderr.strip().splitlines() or ["no output"])[-1]
            out.append(Result(f"inspect:{t}", "", "setup", "", f"(not built offline: {why})"[:200], "", "", "SKIP", ""))
            continue
        out += [Result(**r) for r in rows]
    return out


# ------------------------------------------------------------------ ranking


def ranking(results: list[Result], members: dict[str, list[str]] | None = None) -> str:
    by: dict[str, list[Result]] = defaultdict(list)
    for r in results:
        by[r.grader].append(r)
    rows = []
    status = defaultdict(int)
    for g, rs in by.items():
        setup = next((r for r in rs if r.mode == "setup"), None)
        if setup:
            status[setup.outcome] += 1
            continue
        status["audited"] += 1
        f = findings(rs)
        spec = g.split(":", 1)[1]
        n = len((members or {}).get(spec, [spec]))
        kinds = sorted({r.rewrite for r in f})
        rows.append((len(kinds), n, g, rs[0].sample, kinds))
    rows.sort(key=lambda x: (-x[0] * max(1, x[1]) ** 0.5, x[2]))
    lines = [f"Audited {status['audited']}; no format read {status['NOFORMAT']}; skipped {status['SKIP']}; "
             f"errors {status['ERROR']}.", "",
             "| Grader | Tasks sharing it | Sample | Distinct findings | Rewrites |", "|---|---|---|---|---|"]
    for k, n, g, smp, kinds in rows:
        lines.append(f"| {g} | {n} | {smp} | {k} | {', '.join(kinds) or '-'} |")
    return "\n".join(lines) + "\n"
