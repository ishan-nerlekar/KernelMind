"""Rewrite families for graders that read meaning, not an extracted answer.

Two kinds of check are common in eval code and break in predictable ways:

- **Negation**: does the text claim something happened ("the request was processed") or
  deny it ("was not processed")? Typical bugs: contractions (`wasn't`) and a negation a
  few words back are not seen as negation; a "no-" compound ("No-fee") or a negation in
  another clause is.
- **Dates**: does a quote support a month? Typical bugs: only some formats parse
  (`09/2026`, day-first `15/09/2026`, `15.09.2026` missed), and words that look like
  month names ("rates *may* change") count as months.

Both are discovered, not assumed: the negation family runs only when the grader gives
"was X" and "was not X" different verdicts, and the date family only when it gives the
target month and a different month different verdicts. Then every rewrite has an
expected verdict: the same as the canonical positive, the canonical negative, or "not
the canonical one".
"""

from __future__ import annotations

import calendar
import re

from .core import ERROR, UNSCORED, Result, Sample

# ------------------------------------------------------------------ negation

POSITIVE = "The request was {x}."
NEGATIVE = "The request was not {x}."
# (rewrite, text, expected: "negative" | "positive")
NEGATION_CASES = [
    ("negation_contraction", "The request wasn't {x}.", "negative"),
    ("negation_contraction_perfect", "The request hasn't been {x}.", "negative"),
    ("negation_far", "The request has not yet been fully {x}.", "negative"),
    ("negation_never", "The request was never {x}.", "negative"),
    ("negation_not_yet", "The request is not yet {x}.", "negative"),
    ("compound_no_prefix", "No-fee request {x}.", "positive"),
    ("negation_other_clause", "Not a duplicate: the request was {x}.", "positive"),
    ("negation_after", "The request was {x}, not rejected.", "positive"),
]


def is_predicate(target: str) -> bool:
    t = target.strip()
    return bool(re.fullmatch(r"[a-z][a-z \-]{2,30}", t)) and t not in ("yes", "no", "true", "false")


async def _grade(g, text: str, s: Sample) -> str:
    try:
        return await g.grade(text, s)
    except Exception as e:  # noqa: BLE001
        return f"{ERROR}: {type(e).__name__}: {e}"[:120]


def _outcome(got: str, want: str | None, avoid: str | None = None) -> str:
    if got.startswith(ERROR):
        return "ERROR"
    if want is not None:
        return "ok" if got == want else ("DROP" if got == UNSCORED else "FLIP")
    return "FLIP" if got == avoid else "ok"


async def audit_negation(g, s: Sample) -> list[Result]:
    x = s.target.strip()
    pos, neg = await _grade(g, POSITIVE.format(x=x), s), await _grade(g, NEGATIVE.format(x=x), s)
    if pos == neg or ERROR in pos or ERROR in neg or UNSCORED in (pos, neg):
        return []  # the grader does not read negation of this predicate
    out = []
    for name, tmpl, expected in NEGATION_CASES:
        text = tmpl.format(x=x)
        want = neg if expected == "negative" else pos
        got = await _grade(g, text, s)
        out.append(Result(g.name, s.id, "negation", POSITIVE, name, f"same as '{expected}'", got,
                          _outcome(got, want), text))
    return out


# ------------------------------------------------------------------ dates

MONTH_WORD_LURES = {5: "Rates may change without notice.", 3: "Staff will march to the office."}


def is_date(target: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", target.strip()))


def date_forms(year: int, month: int) -> dict[str, str]:
    name, abbr = calendar.month_name[month], calendar.month_abbr[month]
    last = calendar.monthrange(year, month)[1]
    mm = f"{month:02d}"
    return {
        "canonical": f"{name} {year}",
        "date_month_abbrev": f"{abbr} {year}",
        "date_iso": f"{year}-{mm}-15",
        "date_mm_yyyy": f"{mm}/{year}",
        "date_day_first": f"15/{mm}/{year}",
        "date_dotted": f"15.{mm}.{year}",
        "date_us": f"{mm}/15/{year}",
        "date_day_month_name": f"15 {name} {year}",
        "date_month_day_name": f"{name} 15, {year}",
        "date_range_day_first": f"01/{mm}/{year} - {last}/{mm}/{year}",
    }


DATE_FRAMES = ["Statement period: {d}", "{d}", "Date: {d}"]


async def _date_frame(g, s: Sample, year: int, month: int) -> tuple[str, str] | None:
    other = month % 12 + 1
    for frame in DATE_FRAMES:
        right = await _grade(g, frame.format(d=date_forms(year, month)["canonical"]), s)
        wrong = await _grade(g, frame.format(d=date_forms(year, other)["canonical"]), s)
        if right != wrong and ERROR not in right and right != UNSCORED:
            return frame, right
    return None


async def audit_dates(g, s: Sample) -> list[Result]:
    year, month = int(s.target[:4]), int(s.target[5:7])
    found = await _date_frame(g, s, year, month)
    if found is None:
        return [Result(g.name, s.id, "setup", "", "(no date format read)", "same", "", "NOFORMAT", "")]
    frame, verdict = found
    out = []
    for name, d in date_forms(year, month).items():
        if name == "canonical":
            continue
        text = frame.format(d=d)
        got = await _grade(g, text, s)
        out.append(Result(g.name, s.id, "date", frame, name, "same", got, _outcome(got, verdict), text))
    adjacent = date_forms(year, month % 12 + 1)["date_mm_yyyy"]
    got = await _grade(g, frame.format(d=adjacent), s)
    out.append(Result(g.name, s.id, "date", frame, "date_adjacent_month", "wrong", got,
                      _outcome(got, None, verdict), frame.format(d=adjacent)))
    # words that look like month names: checked for the months they imitate, same year
    for lure_month, lure in MONTH_WORD_LURES.items():
        lure_sample = Sample(f"{year}-{lure_month:02d}", s.choices, s.input, s.metadata, s.output, s.id)
        lf = await _date_frame(g, lure_sample, year, lure_month)
        if lf is None:
            continue
        got = await _grade(g, lure, lure_sample)
        out.append(Result(g.name, s.id, "date", lf[0], f"month_word_lure:{calendar.month_abbr[lure_month]}",
                          "wrong", got, _outcome(got, None, lf[1]), lure))
    return out
