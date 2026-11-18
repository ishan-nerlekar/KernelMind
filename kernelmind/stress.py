"""Scorer stress test: does a grader's verdict survive rewrites that keep the meaning?

A probe wraps one scorer. It knows how to grade a piece of text (a model answer, or a
judge's reply), what verdict the canonical text should get, and which rewrites apply.
Each rewrite produces new text plus the verdict it *should* get:

- "same":  meaning-preserving formatting (bold, a full stop, a capital letter, a code
           fence). The verdict must not change.
- "wrong": a near miss (a hedge naming another option, a superseded draft answer, an
           off-by-a-little number). The verdict must not be the correct one.
- "unscored": the reply carries no verdict (an empty content-filter reply). Any
           definite verdict is a finding; unscored is right.

Outcomes per case: ok, FLIP (a definite verdict other than the expected one), DROP
(expected a verdict, got unscored), ERROR (the scorer raised).

Pure Python: probes that need inspect_ai live in stress_probes.py and import it lazily.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

UNSCORED = "unscored"


@dataclass
class Case:
    rewrite: str
    text: str
    expect: str  # "same" | "wrong" | "unscored"


@dataclass
class Probe:
    name: str
    kind: str  # "answer" or "judge"
    grade: Callable[[str], Awaitable[str]]  # text -> verdict label (or UNSCORED)
    base: str  # canonical text
    verdict: str  # verdict the canonical text must get
    cases: list[Case]
    note: str = ""


@dataclass
class Result:
    probe: str
    kind: str
    rewrite: str
    expect: str
    got: str
    outcome: str  # ok | FLIP | DROP | ERROR | SETUP
    text: str


# ---------------------------------------------------------------- rewrites


def answer_cases(frame: str, answer: str, wrong: str, *, numeric: bool = False, letters: bool = False) -> list[Case]:
    """Rewrites of an answer embedded in `frame` (e.g. "Reasoning...\\nANSWER: {a}")."""
    f = lambda a: frame.format(a=a)  # noqa: E731
    same = {
        "bold_answer": f(f"**{answer}**"),
        "trailing_period": f(f"{answer}."),
        "parentheses": f(f"({answer})"),
        "backticks": f(f"`{answer}`"),
        "trailing_note": f(answer) + "\n\nLet me know if you'd like more detail.",
        "leading_space": f(f"  {answer}"),
    }
    if "ANSWER:" in frame:
        same["bold_label"] = frame.replace("ANSWER:", "**ANSWER:**").format(a=answer)
        same["bold_line"] = frame.replace("ANSWER: {a}", "**ANSWER: {a}**").format(a=answer)
    if not letters:
        same["upper_case"] = f(answer.upper()) if answer.upper() != answer else None
        same["title_case"] = f(answer.title()) if answer.title() != answer else None
    if numeric:
        same["boxed"] = f(f"\\boxed{{{answer}}}")
        same["trailing_zero"] = f(f"{answer}.0")
    wrong_cases = {
        # an earlier correct line, then a final, different answer: the final one counts
        "superseded_draft": f(answer) + f"\n\nWait, I made an error. The correct answer is below.\n" + f(f"**{wrong}**"),
        "hedge": f(f"{answer}, though {wrong} is also plausible"),
    }
    if "ANSWER:" in frame:
        # same, with the final line bolded: "**ANSWER: B**"
        wrong_cases["superseded_draft_bold_line"] = (
            f(answer) + "\n\nWait, I made an error.\n" + frame.replace("ANSWER: {a}", "**ANSWER: {a}**").format(a=wrong)
        )
    if numeric:
        # the right number in the working, an unparseable final answer
        wrong_cases["reasoning_number_unparseable_final"] = (
            f"So far we have {answer} as an intermediate value.\n" + f(f"\\boxed{{{wrong}}}")
        )
    out = [Case(k, v, "same") for k, v in same.items() if v]
    out += [Case(k, v, "wrong") for k, v in wrong_cases.items()]
    return out


def judge_cases(template: str, token: str, *, numeric: bool = False, header: str | None = None) -> list[Case]:
    """Rewrites of a judge reply `template` whose verdict token is `{v}`."""
    t = lambda v: template.replace("{v}", v)  # noqa: E731
    same = {
        "token_bold": t(f"**{token}**"),
        "token_trailing_period": t(f"{token}."),
        "fenced_reply": f"```\n{t(token)}\n```",
        "trailing_note": t(token) + "\n\nI hope this assessment helps.",
    }
    if not numeric:
        same["token_capitalised"] = t(token.capitalize()) if token.capitalize() != token else None
        same["token_upper"] = t(token.upper()) if token.upper() != token else None
        same["token_lower"] = t(token.lower()) if token.lower() != token else None
    else:
        same["token_quoted"] = t(f'"{token}"') if f'"{token}"' not in template.replace("{v}", "") else None
        same["restated_scale"] = "On a scale of 1-10, here is my assessment.\n" + t(token)
    if header:
        same["header_markdown"] = t(token).replace(header, "## " + header.lstrip("#").strip().capitalize())
        same["header_capitalised"] = t(token).replace(header, header[:1] + header[1:].capitalize())
    out = [Case(k, v, "same") for k, v in same.items() if v]
    out.append(Case("empty_reply", "", UNSCORED))
    return out


# ---------------------------------------------------------------- runner


def judge_outcome(expect: str, base_verdict: str, got: str) -> str:
    if expect == "same":
        return "ok" if got == base_verdict else ("DROP" if got == UNSCORED else "FLIP")
    if expect == "wrong":
        return "FLIP" if got == base_verdict else "ok"
    return "ok" if got == UNSCORED else "FLIP"  # expect unscored


async def run_probe(p: Probe) -> list[Result]:
    try:
        got = await p.grade(p.base)
    except Exception as e:  # noqa: BLE001
        got = f"error: {type(e).__name__}: {e}"
    if got != p.verdict:
        return [Result(p.name, p.kind, "(base)", p.verdict, str(got), "SETUP", p.base)]
    results = []
    for c in p.cases:
        try:
            got = await p.grade(c.text)
            outcome = judge_outcome(c.expect, p.verdict, got)
        except Exception as e:  # noqa: BLE001
            got, outcome = f"{type(e).__name__}: {e}"[:80], "ERROR"
        results.append(Result(p.name, p.kind, c.rewrite, c.expect, str(got), outcome, c.text))
    return results


def run(probes: list[Probe]) -> list[Result]:
    async def go():
        out = []
        for p in probes:
            out += await run_probe(p)
        return out
    return asyncio.run(go())


def report(results: list[Result], out_dir: Path | None = None) -> str:
    findings = [r for r in results if r.outcome not in ("ok",)]
    by_probe: dict[str, list[Result]] = {}
    for r in results:
        by_probe.setdefault(r.probe, []).append(r)
    lines = ["| Probe | Cases | Findings |", "|---|---|---|"]
    for name, rs in by_probe.items():
        bad = [f"{r.rewrite} ({r.outcome}: got {r.got})" for r in rs if r.outcome != "ok"]
        lines.append(f"| {name} | {len(rs)} | {'; '.join(bad) or '-'} |")
    md = "\n".join(lines) + f"\n\n{len(findings)} findings in {len(results)} cases across {len(by_probe)} probes.\n"
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "results.json").write_text(json.dumps([asdict(r) for r in results], indent=1))
        (out_dir / "summary.md").write_text(md)
    return md


def compare_known(results: list[Result], known: dict[str, set[str]]) -> dict[str, Any]:
    """Recall against hand-confirmed findings: {probe: {rewrite, ...}}."""
    found = {(r.probe, r.rewrite) for r in results if r.outcome in ("FLIP", "DROP", "SETUP")}
    want = {(p, rw) for p, rws in known.items() for rw in rws}
    return {"known": len(want), "rediscovered": len(want & found), "missed": sorted(want - found),
            "new": sorted(found - want)}
