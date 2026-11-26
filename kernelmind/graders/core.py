"""Audit any grader: does its verdict survive rewrites that keep the meaning?

A grader is anything that turns a model output (plus the sample's correct answer) into a
verdict. The engine treats it as a black box, so the same audit runs on an Inspect scorer,
an lm-eval filter+metric, a Python function or a command-line script; adapters only say
how to call it.

Answer graders (the grader reads the model's output):
  1. Discover which output formats the grader reads: a format is *read* when the correct
     answer and a wrong answer in it get different verdicts. No per-grader code needed.
  2. In each read format, rewrite the correct answer (`stress.answer_cases`): formatting
     that keeps the meaning must keep the verdict; a near miss must not get the correct one.

Judge graders (the grader asks an LLM and parses its reply): the adapter replays scripted
judge replies. Candidate replies are built from the judge prompt itself (its verdict words,
JSON keys, XML tags, `GRADE:` lines); replies that get different verdicts are the canonical
ones, and their rewrites (`stress.judge_cases`) must keep the verdict. Verdict words that
contain one another (CORRECT / INCORRECT, COMPLIANCE / NON-COMPLIANCE) must not collapse.

Outcomes per case: ok, FLIP, DROP, ERROR (as in `stress`). Every finding needs a human look
before it is filed: some "same" rewrites are judgement calls for strict-format evals.
"""

from __future__ import annotations

import inspect
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..stress import UNSCORED, Case, answer_cases, judge_cases, judge_outcome

ERROR = "error"


@dataclass
class Sample:
    target: str
    choices: list[str] | None = None
    input: str = "Answer the question."
    metadata: dict = field(default_factory=dict)
    output: str | None = None  # a real model output, when the sample comes from a log
    id: str = "synthetic"
    frames: list[str] = field(default_factory=list)  # formats to try first ({a} = answer), e.g. the task's own


class Grader(Protocol):
    name: str

    async def grade(self, output: str, sample: Sample) -> str:
        """Verdict label for a model output (UNSCORED if the grader leaves it out)."""

    # Judge graders also implement:
    #   uses_judge(sample) -> bool
    #   async grade_judge(reply, output, sample) -> str   (verdict when the judge says `reply`)
    #   judge_prompt: str                                  (the last prompt sent to the judge)


@dataclass
class Result:
    grader: str
    sample: str
    mode: str  # answer | judge | setup
    frame: str
    rewrite: str
    expect: str
    got: str
    outcome: str  # ok | FLIP | DROP | ERROR | SKIP | NOFORMAT
    text: str


def label(value: Any) -> str:
    """A comparable label for a grader's raw verdict (bool, number, letter, dict...)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return UNSCORED
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return f"{float(value):g}"
    if isinstance(value, dict):
        return ",".join(f"{k}={label(value[k])}" for k in sorted(value))
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(label(v) for v in value) + "]"
    return str(value)


async def call(fn, *args, **kwargs):
    out = fn(*args, **kwargs)
    return await out if inspect.isawaitable(out) else out


# ------------------------------------------------------------------ answer graders

# Output formats graders commonly ask for. {a} is the answer. Each is tried bare and after
# a line of reasoning; the ones the grader actually reads are kept.
FRAMES = [
    "{a}",
    "ANSWER: {a}",
    "Answer: {a}",
    "The answer is {a}.",
    "The answer is ({a}).",
    "The final answer is {a}.",
    "The best answer is {a}",
    "Final Answer: {a}",
    "#### {a}",
    "\\boxed{{{a}}}",
    "[ANSWER]{a}[/ANSWER]",
    "<answer>{a}</answer>",
    "Exact Answer: {a}",
]
REASONING = "Let me work through this step by step.\n"
LEAD_INS = {"A": "After checking each option,", "B": "Based on the options,", "C": "Checking each option,",
            "D": "Double-checking each option,", "E": "Examining each option,", "F": "From the options,",
            "G": "Going through the options,", "H": "Having checked each option,"}


def answer_kind(s: Sample) -> str:
    t = s.target.strip()
    if re.fullmatch(r"[A-Z]", t):
        return "letter"
    if re.fullmatch(r"[A-Z](,\s*[A-Z])+", t):
        return "letters"
    try:
        float(t.replace(",", ""))
        return "number"
    except ValueError:
        return "text"


def wrong_answer(s: Sample, kind: str) -> str:
    t = s.target.strip()
    if kind == "letter":
        n = max(len(s.choices or []), 4)
        letters = [chr(65 + i) for i in range(n)]
        return next(x for x in letters if x != t)
    if kind == "letters":
        return t[0]  # a strict subset
    if kind == "number":
        v = float(t.replace(",", ""))
        w = v * 7 + 3
        return f"{w:g}" if not w.is_integer() else str(int(w))
    if "\\" in t:  # a LaTeX expression: a different, equally parseable one
        return "\\frac{2}{7}" if t != "\\frac{2}{7}" else "\\frac{3}{7}"
    if t.lower() in ("yes", "no"):
        return "no" if t.lower() == "yes" else "yes"
    if t.lower() in ("true", "false"):
        return "false" if t.lower() == "true" else "true"
    return "Lorem"


def text_cases(frame: str, t: str) -> list[Case]:
    """Same text, as models type it: typographic punctuation and spacing that ASCII-only normalisers miss
    (string.punctuation has no ’ or “”), and a leading article that answer normalisers are meant to drop."""
    f = lambda a: frame.format(a=a)  # noqa: E731
    same = {
        "curly_quotes": f(f"“{t}”"),
        "curly_apostrophe": f(t.replace("'", "’")) if "'" in t else None,
        "en_dash": f(t.replace("-", "–")) if "-" in t else None,
        "nbsp": f(t.replace(" ", " ")) if " " in t else None,
        "leading_article": f(f"The {t}") if not re.match(r"(?i)(the|a|an)\s", t) else None,
    }
    return [Case(k, v, "same") for k, v in same.items() if v]


async def _safe(g: Grader, text: str, s: Sample) -> str:
    try:
        return await g.grade(text, s)
    except Exception as e:  # noqa: BLE001
        return f"{ERROR}: {type(e).__name__}: {e}"[:120]


async def discover_frames(g: Grader, s: Sample, limit: int = 3) -> list[tuple[str, str]]:
    """Formats the grader reads: [(frame, verdict for the correct answer)]."""
    kind = answer_kind(s)
    wrong = wrong_answer(s, kind)
    found = []
    for base in dict.fromkeys(s.frames + FRAMES):
        for frame in (REASONING + base, base):
            right = await _safe(g, frame.format(a=s.target), s)
            if right.startswith(ERROR) or right == UNSCORED:
                continue
            if right != await _safe(g, frame.format(a=wrong), s):
                found.append((frame, right))
                break  # one variant per format is enough
        if len(found) >= limit:
            break
    return found


async def audit_answers(g: Grader, s: Sample, limit: int = 3) -> list[Result]:
    frames = await discover_frames(g, s, limit)
    if not frames:
        return [Result(g.name, s.id, "setup", "", "(no format read)", "same", "", "NOFORMAT", "")]
    kind = answer_kind(s)
    wrong = wrong_answer(s, kind)
    out = []
    for frame, verdict in frames:
        cases = answer_cases(frame, s.target, wrong, numeric=kind == "number", letters=kind.startswith("letter"))
        if kind == "number" and "." in s.target:  # 0.25 -> 0.250, not 0.25.0
            cases = [Case(c.rewrite, frame.format(a=s.target + "0"), c.expect) if c.rewrite == "trailing_zero" else c
                     for c in cases]
        if "\\" in s.target:  # LaTeX answer: \Frac is not a case variant of \frac
            cases = [c for c in cases if c.rewrite not in ("upper_case", "title_case")]
        if "\\boxed{" in frame:
            # decoration belongs around the box, not inside it ("\boxed{18.}" is not how models write)
            inner = {"bold_answer", "trailing_period", "parentheses", "backticks", "leading_space"}
            boxed = frame.format(a=s.target).rsplit("\n", 1)[-1]
            head = frame.format(a=s.target)[: -len(boxed)]
            cases = [c for c in cases if c.rewrite not in inner] + [
                Case("boxed_bold", f"{head}**{boxed}**", "same"),
                Case("boxed_trailing_period", f"{head}{boxed}.", "same"),
                Case("boxed_in_math", f"{head}${boxed}$", "same")]
        if kind == "letter":
            # a lead-in sentence whose first word starts with another option's letter
            lead = LEAD_INS.get(wrong, "Based on the options,")
            cases.append(Case("lead_in_capital", f"{lead} {frame.format(a=s.target)}", "same"))
        if kind == "number" and re.fullmatch(r"-?\d+", s.target.strip()) and abs(int(s.target)) > 10:
            cases.append(Case("off_by_3", frame.format(a=str(int(s.target) - 3)), "wrong"))
        if kind == "text" and "\\" not in s.target:
            cases += text_cases(frame, s.target)
        if kind == "letters":
            parts = [p.strip() for p in s.target.split(",")]
            cases += [Case("comma_space", frame.format(a=", ".join(parts)), "same"),
                      Case("space_separated", frame.format(a=" ".join(parts)), "same"),
                      Case("reordered", frame.format(a=",".join(reversed(parts))), "same")]
        for c in cases:
            got = await _safe(g, c.text, s)
            outcome = "ERROR" if got.startswith(ERROR) else judge_outcome(c.expect, verdict, got)
            out.append(Result(g.name, s.id, "answer", frame, c.rewrite, c.expect, got, outcome, c.text))
    return out


# ------------------------------------------------------------------ judge graders

VERDICT_WORDS = {"CORRECT", "INCORRECT", "NOT_ATTEMPTED", "YES", "NO", "TRUE", "FALSE", "PASS", "FAIL", "SAFE",
                 "UNSAFE", "COMPLIANCE", "NON-COMPLIANCE", "REFUSAL", "ACCEPTABLE", "UNACCEPTABLE"}
COMMON_TOKENS = ["CORRECT", "INCORRECT", "yes", "no", "y", "n", "safe", "unsafe", "A", "B", "C", "1", "0", "5", "8"]
_STOP = {"I", "AI", "JSON", "OK", "NOT", "THE", "AND", "OR", "IF", "DO", "YOUR", "YOU", "USER", "ONLY", "MUST"}


def judge_vocabulary(prompt: str) -> list[str]:
    caps = re.findall(r"(?<![\w-])[A-Z][A-Z_]+(?:-[A-Z_]+)*(?![\w-])", prompt)
    quoted = re.findall(r"[\"'`]([A-Za-z][A-Za-z_\-]{0,19})[\"'`]", prompt)
    words = []
    for w in caps + quoted + COMMON_TOKENS:
        if w in words or (w.upper() in _STOP | {"GRADE"} and w not in COMMON_TOKENS):
            continue
        words.append(w)
    return words[:40]


def judge_templates(prompt: str) -> list[str]:
    """Reply templates ({v} = verdict token) suggested by the judge prompt."""
    t = ["{v}"]
    if re.search(r"\bGRADE\b", prompt, re.I):
        t.append("GRADE: {v}")
    for key in dict.fromkeys(re.findall(r'"(\w{1,30})"\s*:', prompt)):
        t += ['{"' + key + '": "{v}"}', '{"' + key + '": {v}}']
    for tag in dict.fromkeys(re.findall(r"<(\w{1,30})>", prompt)):
        if f"</{tag}>" in prompt:
            t.append(f"<{tag}>{{v}}</{tag}>")
    for key in dict.fromkeys(re.findall(r"(?m)^\s*([a-z][a-z_ ]{1,30}):", prompt)):
        t.append(f"{key}: {{v}}")
    t += _format_blocks(prompt)
    return t[:25]


_VALUE_SLOT = re.compile(r"answer|score|rating|grade|label|verdict|number|digit|decision", re.I)


def _format_blocks(prompt: str) -> list[str]:
    """Output formats spelled out in the prompt as lines with <placeholders>: the value
    slots become {v}, the rest a short sentence."""
    lines, blocks, cur = prompt.splitlines(), [], []
    for line in lines + [""]:
        if re.search(r"<[^<>\n]{3,200}>", line) or (cur and re.fullmatch(r"\s*#?\w[\w.]*\s*", line)):
            cur.append(line)
            continue
        if sum(bool(re.search(r"<[^<>\n]{3,200}>", x)) for x in cur) >= 2:
            blocks.append(cur)
        cur = []
    out = []
    for b in blocks:
        text = "\n".join(b)
        if not _VALUE_SLOT.search(text):
            continue
        filled = re.sub(r"<([^<>\n]{3,200})>",
                        lambda m: "{v}" if _VALUE_SLOT.search(m.group(1)) and not re.search(r"reason", m.group(1), re.I)
                        else "Brief reasoning.", text)
        out.append(filled)
        if filled.count("{v}") >= 2:  # slots often take different ranges (a 0/1 flag, then 1-5 scores)
            out += [filled.replace("{v}", "0", 1), filled.replace("{v}", "1", 1)]
    return out[:6]


def _separator_variants(tok: str) -> dict[str, str]:
    """Other spellings of a multi-word verdict: NOT_ATTEMPTED, NOT ATTEMPTED, NON-COMPLIANCE..."""
    v = {}
    if "_" in tok:
        v["token_separator_space"] = tok.replace("_", " ")
    if "-" in tok:
        v["token_separator_space"] = tok.replace("-", " ")
        v["token_separator_none"] = tok.replace("-", "")
    m = re.fullmatch(r"(NON|NOT|UN)([A-Z]{3,})", tok)
    if m:
        v["token_separator_hyphen"] = f"{m.group(1)}-{m.group(2)}"
    return v


async def _judge(g, reply: str, output: str, s: Sample) -> str:
    try:
        return await g.grade_judge(reply, output, s)
    except Exception as e:  # noqa: BLE001
        return f"{ERROR}: {type(e).__name__}: {e}"[:120]


def _opposites(a: str, b: str) -> bool:
    x, y = a.lower(), b.lower()
    return x != y and len(x) > 1 and len(y) > 1 and (x in y or y in x)


async def audit_judge(g, s: Sample, output: str | None = None) -> list[Result]:
    output = output or s.output or f"The answer is {s.target}."
    await _judge(g, "UNSURE", output, s)  # capture the judge prompt
    prompt = getattr(g, "judge_prompt", "") or ""
    tokens, templates = judge_vocabulary(prompt), judge_templates(prompt)
    seen: dict[tuple[str, str], str] = {}
    for tmpl in templates:
        for tok in tokens:
            seen[(tmpl, tok)] = await _judge(g, tmpl.replace("{v}", tok), output, s)
    definite = {k: v for k, v in seen.items() if v != UNSCORED and not v.startswith(ERROR)}
    labels = set(definite.values())
    if len(labels) < 2:
        return [Result(g.name, s.id, "setup", "", "(no reply format found)", "same", ",".join(sorted(labels)),
                       "NOFORMAT", "")]
    # canonical reply per verdict: prefer a structured template over a bare token
    canon: dict[str, tuple[str, str]] = {}
    for (tmpl, tok), v in sorted(definite.items(), key=lambda kv: kv[0][0] == "{v}"):
        canon.setdefault(v, (tmpl, tok))
    out: list[Result] = []
    # verdict words the prompt names that contain one another must not collapse to one
    # verdict (unless that verdict is just what the template gives any unknown word)
    named = [t for t in tokens if re.search(rf"(?<![\w-]){re.escape(t)}(?![\w-])", prompt)]
    for tmpl in templates:
        fallback = await _judge(g, tmpl.replace("{v}", "zzqx"), output, s)
        for a in named:
            for b in named:
                va, vb = definite.get((tmpl, a)), definite.get((tmpl, b))
                if a < b and va and va == vb and va != fallback and _opposites(a, b):
                    out.append(Result(g.name, s.id, "judge", tmpl, f"token_collision:{a}/{b}", "distinct", va,
                                      "FLIP", tmpl.replace("{v}", a) + " | " + tmpl.replace("{v}", b)))
    # a verdict word the prompt asks for that reads as "unknown" while other words are read
    reported = set()
    for tmpl in templates:
        fallback = await _judge(g, tmpl.replace("{v}", "zzqx"), output, s)
        read = [t for t in named if definite.get((tmpl, t)) not in (None, fallback)]
        if not read:
            continue
        for w in named:
            partners = [p for p in read if _opposites(w, p)]
            if partners and all(definite.get((tmpl, p)) != definite.get((tmpl, w)) for p in partners):
                continue  # e.g. "safe" scores like an unparsed reply only because safe is the default
            if w.upper() in VERDICT_WORDS and w not in read and w not in reported:
                reported.add(w)
                out.append(Result(g.name, s.id, "judge", tmpl, f"unread_verdict_word:{w}", "read",
                                  seen.get((tmpl, w), ""), "FLIP", tmpl.replace("{v}", w)))
    for verdict, (tmpl, tok) in canon.items():
        header = next((h for h in re.findall(r"(?m)^(#\w+)\s*$", tmpl)), None)
        cases = judge_cases(tmpl, tok, numeric=tok.isdigit(), header=header)
        cases += [Case(k, tmpl.replace("{v}", w), "same") for k, w in _separator_variants(tok).items()]
        cases.append(Case("with_reason", tmpl.replace("{v}", tok) + "\nThe reasoning is sound, so my verdict stays.",
                          "same"))
        for c in cases:
            got = await _judge(g, c.text, output, s)
            outcome = "ERROR" if got.startswith(ERROR) else judge_outcome(c.expect, verdict, got)
            out.append(Result(g.name, s.id, "judge", tmpl.replace("{v}", tok), c.rewrite, c.expect, got, outcome,
                              c.text))
    return out


async def audit(g, s: Sample) -> list[Result]:
    from .semantic import audit_dates, audit_negation, is_date, is_predicate

    uses_judge = getattr(g, "uses_judge", None)
    if uses_judge is not None and await call(uses_judge, s):
        return await audit_judge(g, s)
    if is_date(s.target):
        return await audit_dates(g, s)
    out = await audit_answers(g, s)
    if is_predicate(s.target):
        negation = await audit_negation(g, s)
        if negation:  # the grader reads negation: that, not answer formats, is what it checks
            out = negation
    return out


# ------------------------------------------------------------------ reporting


def findings(results: list[Result]) -> list[Result]:
    return [r for r in results if r.outcome in ("FLIP", "DROP", "ERROR")]


def report(results: list[Result], out_dir: Path | None = None) -> str:
    by: dict[str, list[Result]] = {}
    for r in results:
        by.setdefault(r.grader, []).append(r)
    lines = ["| Grader | Cases | Findings |", "|---|---|---|"]
    for name, rs in by.items():
        setup = [r for r in rs if r.mode == "setup"]
        if setup:
            lines.append(f"| {name} | 0 | {setup[0].outcome}: {setup[0].rewrite} |")
            continue
        bad = sorted({f"{r.rewrite} ({r.outcome}: got {r.got})" for r in findings(rs)})
        lines.append(f"| {name} | {len(rs)} | {'; '.join(bad) or '-'} |")
    md = "\n".join(lines) + f"\n\n{len(findings(results))} findings in {len(results)} cases across {len(by)} graders.\n"
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "results.json").write_text(json.dumps([asdict(r) for r in results], indent=1))
        (out_dir / "summary.md").write_text(md)
    return md


def recall(results: list[Result], known: dict[str, set[str]]) -> dict[str, Any]:
    """Known findings {grader: {rewrite or rewrite-prefix}} re-found by the audit."""
    found = {(r.grader, r.rewrite) for r in findings(results)}
    hits, missed = [], []
    for grader, rewrites in known.items():
        for rw in rewrites:
            ok = any(g == grader and (r == rw or r.startswith(rw)) for g, r in found)
            (hits if ok else missed).append((grader, rw))
    return {"known": len(hits) + len(missed), "rediscovered": len(hits), "missed": sorted(missed)}
