"""Re-read the answers in finished Inspect logs and count verdicts a robust parser would change.

For each sample: the verdict the log recorded, and the verdict from a robust re-reading
of the same text. Nothing is re-run. Two readers so far:

- "choice": multiple choice scored by inspect's choice() (GPQA-style). Robust reading: the
  LAST `ANSWER:` line wins, Markdown emphasis, backticks, parentheses and trailing text
  around the letter are ignored, and the letter must be one of the sample's choices.
- "grader_word": a judge asked for a single word CORRECT/INCORRECT, read from the score's
  explanation (Epoch's Mock AIME grader). Robust reading: the last whole word CORRECT or
  INCORRECT, any case, formatting ignored.

Needs inspect_ai to read .eval files.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_FMT = re.compile(r"[*_`~]")
_ANSWER_LINE = re.compile(r"(?im)^[^\S\n]*(?:final[^\S\n]+)?answer[^\S\n]*:[^\S\n]*(.+)$")


def read_choice(text: str, letters: str) -> str | None:
    """Letter from the last ANSWER line, or None if there isn't a readable one."""
    lines = _ANSWER_LINE.findall(_FMT.sub("", text))
    if not lines:
        return None
    m = re.match(r"\s*[(\[]?\s*([A-Z])\b", lines[-1])
    return m.group(1) if m and m.group(1) in letters else None


def read_grader_word(text: str) -> str | None:
    words = re.findall(r"\b(INCORRECT|CORRECT)\b", _FMT.sub("", text).upper())
    return words[-1] if words else None


@dataclass
class Row:
    log: str
    model: str
    sample: str
    epoch: int
    recorded: str  # "C" / "I" / other
    robust: str  # "C" / "I" / "unparsed"


def _verdict(v) -> str:
    return v if v in ("C", "I") else str(v)


def rows_from_log(path: Path, reader: str = "choice", scorer: str | None = None) -> Iterable[Row]:
    from inspect_ai.log import read_eval_log

    log = read_eval_log(str(path))
    model = log.eval.model
    for s in log.samples or []:
        if not s.scores:
            continue
        name = scorer or next(iter(s.scores))
        sc = s.scores[name]
        target = s.target if isinstance(s.target, str) else ",".join(s.target)
        if reader == "choice":
            letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[: len(s.choices or [])] or "ABCD"
            got = read_choice(s.output.completion or "", letters)
            robust = "unparsed" if got is None else ("C" if got == target.strip() else "I")
        else:  # grader_word
            word = read_grader_word(sc.explanation or "")
            robust = {"CORRECT": "C", "INCORRECT": "I"}.get(word, "unparsed")
        yield Row(str(path.name), model, str(s.id), s.epoch, _verdict(sc.value), robust)


def summarize(rows: list[Row]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for model in sorted({r.model for r in rows}):
        rs = [r for r in rows if r.model == model]
        c = Counter((r.recorded, r.robust) for r in rs)
        n = len(rs)
        rec = sum(r.recorded == "C" for r in rs) / n
        # robust score: unparsed counted wrong, so the change comes only from re-read verdicts
        rob = sum(r.robust == "C" for r in rs) / n
        out[model] = {
            "samples": n,
            "recorded_score": rec,
            "robust_score": rob,
            "wrong_to_right": c[("I", "C")],  # recorded I, robust reading says C
            "right_to_wrong": c[("C", "I")],
            "right_but_unparsed": c[("C", "unparsed")],
            "wrong_and_unparsed": c[("I", "unparsed")],
        }
    return out


def markdown(summary: dict[str, dict]) -> str:
    lines = ["| Model | Samples | Recorded | Robust | I→C | C→I | Unparsed (C / I) |", "|---|---|---|---|---|---|---|"]
    for m, d in summary.items():
        lines.append(f"| {m} | {d['samples']} | {d['recorded_score']:.4f} | {d['robust_score']:.4f} | "
                     f"{d['wrong_to_right']} | {d['right_to_wrong']} | {d['right_but_unparsed']} / {d['wrong_and_unparsed']} |")
    return "\n".join(lines) + "\n"
