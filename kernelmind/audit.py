"""Audit someone else's task verifier with candidate solutions whose correct verdict we know.

For each task, candidates are written into a copy of the task and graded by `validate`:
  - mutants: small mechanical changes to the reference solve.sh            (should fail)
  - near misses: model-written solutions that break one stated requirement  (should fail)
  - alternatives: model-written solutions that meet every requirement      (should pass)
A near miss or mutant that passes is a *lenient* suspect; an alternative that fails is a *strict*
suspect. Suspects are not findings until confirmed by hand (see docs/AUDIT.md). The model sees the
instruction and the reference solution, never the tests.
"""
from __future__ import annotations

import json
import random
import re
import shutil
from dataclasses import asdict
from pathlib import Path

from .task import Task, load_task
from .validate import validate_task

CATEGORIES = {
    "partial": "meets most requirements but misses one",
    "edge-case": "wrong on a boundary or special case the instruction states or clearly implies",
    "symptom": "makes the obvious check work without the behavior the instruction asks for",
    "over-broad": "does something the instruction forbids, or changes behavior it says to keep",
    "hardcoded": "hardcodes results for the likely inputs instead of solving the task generally",
    "format": "right content but the wrong format, name or location the instruction specifies",
}

PROMPT = """You are auditing the grader of a benchmark task. An AI agent receives the instruction below and \
works in a Linux container (working directory /app, network available). Its work is graded by hidden tests \
that check the final state of the container. Below is the reference solution, a bash script run in /app.

Write two kinds of complete bash scripts (each starts with #!/bin/bash and runs in /app):

1. {n_wrong} NEAR MISSES: what a capable but careless engineer might plausibly submit. Each must violate the \
instruction in exactly one specific way, so that by the instruction's own words it is NOT a correct solution. \
Use a different category for each, from:
{categories}
For each, quote the exact instruction sentence it violates.

2. {n_alt} ALTERNATIVES: solutions that satisfy every requirement in the instruction but differ substantially \
from the reference (a different algorithm, tool or library, or different choices wherever the instruction \
leaves them open, such as unspecified names, ordering or intermediate files). Say what differs and why the \
instruction allows it.

Don't guess what the tests check; work from the instruction. Keep dependencies close to the reference's.
Reply with JSON only:
{{"near_misses": [{{"category": "...", "violates": "...", "solve_sh": "..."}}],
 "alternatives": [{{"differs": "...", "solve_sh": "..."}}]}}

=== INSTRUCTION ===
{instruction}

=== REFERENCE SOLUTION (solve.sh) ===
{reference}
"""

_SKIP = re.compile(r"https?://|install|==\s*\d|pip |apt|uv |^\s*#|@\d|\bversion\b", re.I)
CODE_OPS = (("<=", "<"), (">=", ">"), ("==", "!="), ("!=", "=="), (" < ", " <= "), (" > ", " >= "))
SHELL_OPS = (("-lt", "-le"), ("-le", "-lt"), ("-gt", "-ge"), ("-ge", "-gt"), ("-eq", "-ne"), ("-ne", "-eq"))
_HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")


def mutants(text: str, seed: str, n: int = 6) -> list[tuple[str, str]]:
    """Up to n single-site mutations of a solve.sh, chosen deterministically from seed."""
    lines = text.splitlines(keepends=True)
    sites, end = [], None
    for i, line in enumerate(lines):
        shell_level = end is None
        if end is not None and line.strip() == end:
            end = None
            continue
        if shell_level and (m := _HEREDOC.search(line)):
            end = m.group(1)
        if _SKIP.search(line) or i == 0:
            continue
        for m in re.finditer(r"(?<![\w.])(\d+)(?![\w.])", line):
            sites.append(("number", i, m.start(), m.end(), str(int(m.group(1)) + 1)))
        # At shell level < and > are redirects; only test operators are comparisons there.
        ops = SHELL_OPS if shell_level else CODE_OPS
        for op, new in ops:
            for m in re.finditer(re.escape(op), line):
                sites.append(("compare", i, m.start(), m.end(), new))
        for word, new in (("True", "False"), ("False", "True"), ("true", "false"), ("false", "true")):
            for m in re.finditer(rf"\b{word}\b", line):
                sites.append(("boolean", i, m.start(), m.end(), new))
        if shell_level and line.strip() and not _HEREDOC.search(line):
            sites.append(("delete-step", i, 0, len(line), ""))
    rng = random.Random(seed)
    rng.shuffle(sites)
    by_line: dict[int, list] = {}
    for site in sites:
        by_line.setdefault(site[1], []).append(site)
    lines_order = list(by_line)
    rng.shuffle(lines_order)
    spread = []  # round-robin over lines, so mutants don't pile up on one line
    while len(spread) < min(n, len(sites)):
        for ln in lines_order:
            if by_line[ln] and len(spread) < n:
                spread.append(by_line[ln].pop())
    out = []
    for kind, i, a, b, new in spread:
        mutated = lines.copy()
        mutated[i] = "" if kind == "delete-step" else lines[i][:a] + new + lines[i][b:]
        out.append((f"mut-{len(out) + 1}-{kind}-L{i + 1}", "".join(mutated)))
    return out


def _parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0), strict=False) if m else {}  # scripts often contain raw newlines


def llm_candidates(task: Task, model: str, n_wrong: int, n_alt: int) -> tuple[dict, float]:
    import litellm
    reference = (task.root / "solution" / "solve.sh").read_text()[:15000]
    prompt = PROMPT.format(n_wrong=n_wrong, n_alt=n_alt, instruction=task.instruction[:8000], reference=reference,
                           categories="\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items()))
    r = litellm.completion(model=model, messages=[{"role": "user", "content": prompt}], max_tokens=16000,
                           temperature=0.7)
    try:
        cost = float(litellm.completion_cost(r))
    except Exception:
        cost = 0.0
    return _parse(r.choices[0].message.content or ""), cost


def prepare(task: Task, out: Path, model: str | None, n_mut: int, n_wrong: int, n_alt: int) -> tuple[Task, float]:
    """Copy the task to out/<id>/ with candidates as controls (should fail) and alternatives (should pass)."""
    dst = out / "tasks" / task.id
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(task.root, dst, ignore=shutil.ignore_patterns("alternatives", "controls"))
    ref_dir = task.root / "solution"
    meta, cost = {}, 0.0

    def write(kind: str, name: str, script: str, info: dict) -> None:
        d = dst / kind / name
        shutil.copytree(ref_dir, d)  # keep any files the reference solution ships next to solve.sh
        (d / "solve.sh").write_text(script if script.endswith("\n") else script + "\n")
        meta[name] = {"kind": kind, **info}

    for name, script in mutants((ref_dir / "solve.sh").read_text(), task.id, n_mut):
        write("controls", name, script, {"source": "mutant"})
    if model and (n_wrong or n_alt):
        gen, cost = llm_candidates(task, model, n_wrong, n_alt)
        for i, c in enumerate(gen.get("near_misses", [])[:n_wrong], 1):
            cat = re.sub(r"[^a-z-]", "", str(c.get("category", "near-miss")).lower()) or "near-miss"
            write("controls", f"near-{i}-{cat}", c.get("solve_sh", ""), {"source": "llm", "category": cat,
                                                                          "violates": c.get("violates", "")})
        for i, c in enumerate(gen.get("alternatives", [])[:n_alt], 1):
            write("alternatives", f"alt-{i}", c.get("solve_sh", ""), {"source": "llm", "differs": c.get("differs", "")})
    (dst / "audit_candidates.json").write_text(json.dumps(meta, indent=1))
    return load_task(dst), cost


def classify(checks, meta: dict) -> dict:
    """Turn validate's checks into audit outcomes."""
    rows, ref_ok = [], True
    for c in checks:
        if c.subject in ("starter", "reference"):
            ref_ok &= c.ok
            continue
        info = meta.get(c.subject, {})
        if c.verdict is None:
            outcome = "broken-candidate"  # its solve.sh crashed or infra failed: says nothing about the grader
        elif c.kind == "control":
            outcome = "lenient-suspect" if c.verdict.passed else "caught"
        else:
            outcome = "accepted" if c.verdict.passed else "strict-suspect"
        rows.append({"candidate": c.subject, "kind": c.kind, "outcome": outcome, **info,
                     "failed_checks": c.verdict.failed_checks if c.verdict else [], "note": c.reason[:300]})
    return {"baseline_ok": ref_ok, "candidates": rows}


def audit_task(task: Task, out: Path, backend: str, model: str | None, n_mut: int, n_wrong: int, n_alt: int) -> tuple[dict, float]:
    copy, cost = prepare(task, out, model, n_mut, n_wrong, n_alt)
    checks = validate_task(copy, backend)
    meta = json.loads((copy.root / "audit_candidates.json").read_text())
    result = {"task": task.id, "category": task.meta.get("root_cause"), "generation_cost": cost,
              **classify(checks, meta), "checks": [{**asdict(c), "verdict": c.verdict.to_dict() if c.verdict else None}
                                                   for c in checks]}
    (out / f"{task.id}.json").write_text(json.dumps(result, indent=1, default=str))
    return result, cost


def summary_rows(results: list[dict]) -> list[str]:
    head = ["| Task | Baseline | Mutants caught | Near misses caught | Alternatives accepted | Suspects |",
            "|---|---|---|---|---|---|"]
    rows = []
    for r in results:
        c = r["candidates"]

        def frac(pred, good):
            xs = [x for x in c if pred(x) and x["outcome"] != "broken-candidate"]
            return f"{sum(x['outcome'] == good for x in xs)}/{len(xs)}"
        sus = [x["candidate"] for x in c if x["outcome"].endswith("suspect")]
        rows.append(f"| {r['task']} | {'ok' if r['baseline_ok'] else 'BROKEN'} "
                    f"| {frac(lambda x: x.get('source') == 'mutant', 'caught')} "
                    f"| {frac(lambda x: x['kind'] == 'control' and x.get('source') == 'llm', 'caught')} "
                    f"| {frac(lambda x: x['kind'] == 'alternative', 'accepted')} | {', '.join(sus) or '-'} |")
    return head + rows
