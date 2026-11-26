import asyncio
import re

from kernelmind.graders.adapters import CommandGrader, PythonGrader
from kernelmind.graders.core import (UNSCORED, Sample, audit, audit_answers, audit_judge, discover_frames,
                                     findings, judge_templates, judge_vocabulary, label, recall)


def run(coro):
    return asyncio.run(coro)


class Fn:
    def __init__(self, name, fn):
        self.name, self.fn = name, fn

    async def grade(self, output, sample):
        return label(self.fn(output, sample.target))


def first_hash(output, target):  # gsm8k-style strict match: first "#### N" wins
    m = re.findall(r"#### (\-?[0-9\.\,]+)", output)
    return (m[0].strip() == target) if m else False


def robust_letter(output, target):  # last "ANSWER:" with formatting ignored
    t = re.sub(r"[*_`()]", "", output)
    m = re.findall(r"answer\s*:\s*([A-Z])\b", t, re.I)
    return bool(m) and m[-1].upper() == target


def test_label_normalises_verdict_types():
    assert label(True) == "1" and label(0.5) == "0.5" and label(float("nan")) == UNSCORED
    assert label({"b": 1, "a": "C"}) == "a=C,b=1" and label(None) == UNSCORED


def test_discovers_only_formats_the_grader_reads():
    frames = run(discover_frames(Fn("g", first_hash), Sample("18")))
    assert frames and all("####" in f for f, _ in frames)
    assert run(discover_frames(Fn("never", lambda o, t: False), Sample("18"))) == []


def test_strict_grader_findings_and_robust_grader_clean():
    bad = {r.rewrite for r in findings(run(audit_answers(Fn("g", first_hash), Sample("18"))))}
    assert {"bold_answer", "superseded_draft"} <= bad  # "#### **18**" fails; first "####" wins
    good = findings(run(audit_answers(Fn("g", robust_letter), Sample("C", choices=list("ABCD")))))
    assert not [r for r in good if r.rewrite in ("bold_answer", "bold_label", "backticks", "superseded_draft")]


def test_given_frame_is_tried_first():
    def result_eq(output, target):  # reads only a format no built-in frame uses
        m = re.findall(r"RESULT=(\S+)", output)
        return bool(m) and m[-1] == target
    assert run(discover_frames(Fn("g", result_eq), Sample("18"))) == []
    frames = run(discover_frames(Fn("g", result_eq), Sample("18", frames=["RESULT={a}"])))
    assert frames and "RESULT={a}" in frames[0][0]


def test_no_format_is_reported_not_crashed():
    res = run(audit_answers(Fn("never", lambda o, t: False), Sample("18")))
    assert res[0].outcome == "NOFORMAT"


class FakeJudge:
    """Reads '<label>X</label>'; a substring test makes NON-COMPLIANCE read as COMPLIANCE."""
    name = "fake_judge"
    judge_prompt = ""

    def uses_judge(self, sample):
        return True

    async def grade_judge(self, reply, output, sample):
        self.judge_prompt = 'Answer with <label>COMPLIANCE</label> or <label>NON-COMPLIANCE</label>.'
        m = re.search(r"<label>(.*?)</label>", reply)
        if not m:
            return UNSCORED
        return "COMPLIANCE" if "COMPLIANCE" in m.group(1) else "OTHER"


def test_judge_prompt_vocabulary_and_templates():
    p = 'Reply as JSON {"label": "safe"} or {"label": "unsafe"}. Use <verdict>YES</verdict>. GRADE: C'
    assert {"safe", "unsafe", "YES"} <= set(judge_vocabulary(p))
    t = judge_templates(p)
    assert '{"label": "{v}"}' in t and "<verdict>{v}</verdict>" in t and "GRADE: {v}" in t


def test_judge_token_collision_found():
    res = run(audit(FakeJudge(), Sample("")))
    assert any(r.rewrite.startswith("token_collision") for r in findings(res))
    assert recall(res, {"fake_judge": {"token_collision"}})["rediscovered"] == 1


def test_python_and_command_adapters(tmp_path):
    f = tmp_path / "g.py"
    f.write_text("def grade(output, target):\n    return output.strip().endswith(target)\n")
    g = PythonGrader(f"{f}:grade")
    assert run(g.grade("ANSWER: 7", Sample("7"))) == "1"
    c = CommandGrader("grep -q {target} && echo pass || echo fail")
    assert run(c.grade("the answer is 42", Sample("42"))) == "pass"
    assert run(c.grade("no", Sample("42"))) == "fail"


def test_python_adapter_loads_a_grader_file_on_its_own(tmp_path):
    # a package whose __init__ needs a missing heavy dependency, a sibling helper, and a dependency that is missing
    pkg = tmp_path / "rl_lib" / "rewards"
    pkg.mkdir(parents=True)
    (tmp_path / "rl_lib" / "__init__.py").write_text("import torch_that_is_not_installed\n")
    (pkg / "__init__.py").write_text("import torch_that_is_not_installed\n")
    (pkg / "helpers.py").write_text("def last_hash(s):\n    import re\n    m = re.findall(r'#### (\\S+)', s)\n"
                                    "    return m[-1] if m else None\n")
    (pkg / "gsm.py").write_text(
        "from typing import Optional\nimport fancy_tokenizer_missing as tk\nfrom rl_lib.rewards.helpers import last_hash\n\n"
        "@tk.register('gsm')\n"
        "def compute_score(solution_str, ground_truth, method='strict', score=1.0):\n"
        "    return {'score': score if last_hash(solution_str) == ground_truth else 0.0, 'pred': last_hash(solution_str)}\n\n"
        "class Verifier:\n"
        "    def __call__(self, tokenized_prediction, prediction, label, query=None):\n"
        "        return type('R', (), {'score': float(last_hash(prediction) == label)})()\n\n"
        "def trl_reward(completions, solution, **kwargs):\n"
        "    return [float(last_hash(c[0]['content']) == s) for c, s in zip(completions, solution)]\n\n"
        "def extract(text, marker='####'):\n"
        "    return last_hash(text)\n\n"
        "def pair(response, answer):\n"
        "    return last_hash(response) == answer, last_hash(response)\n")
    f = pkg / "gsm.py"
    g = PythonGrader(f"{f}:compute_score?score=2")
    assert g.stubbed == ["fancy_tokenizer_missing"]
    assert run(g.grade("#### 7", Sample("7"))) == "2" and run(g.grade("#### 8", Sample("7"))) == "0"
    for name in ("Verifier", "trl_reward", "extract", "pair"):
        g = PythonGrader(f"{f}:{name}")
        assert run(g.grade("#### 7", Sample("7"))) == "1", name
        assert run(g.grade("#### 8", Sample("7"))) == "0", name
    bad = {r.rewrite for r in findings(run(audit_answers(PythonGrader(f"{f}:compute_score"), Sample("18"))))}
    assert "bold_answer" in bad  # the audit runs end to end on a file loaded this way


# ---------------------------------------------------------------- negation and date families

NEG = {"not", "never", "no"}


def window_negation(output, target):  # bug pattern: plain negators only, within 3 words
    for m in re.finditer(rf"\b{re.escape(target)}\b", output):
        words = re.findall(r"[a-z]+", re.split(r"[,.;:!?]", output[: m.start()])[-1].lower())[-3:]
        if not NEG & set(words):
            return "claims"
    return "no_claim"


def robust_negation(output, target):  # contractions, any distance in the clause, compounds not negators
    for m in re.finditer(rf"\b{re.escape(target)}\b", output):
        clause = re.split(r"[,.;:!?]", output[: m.start()])[-1].lower()
        clause = re.sub(r"\bno-\w+", " ", clause)
        if not re.search(r"\b(not|never|no)\b|n't\b", clause):
            return "claims"
    return "no_claim"


MONTHS = {m.lower(): i for i, m in enumerate(__import__("calendar").month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(__import__("calendar").month_abbr) if m})


def us_dates_only(output, target):  # bug pattern: month-first numeric dates, any month word counts
    y, mo = int(target[:4]), int(target[5:7])
    found = {(int(a), int(b)) for b, a in re.findall(r"\b(\d{1,2})/\d{1,2}/(\d{4})\b", output)}
    found |= {(int(a), int(b)) for a, b in re.findall(r"\b(\d{4})-(\d{2})", output)}
    words = {MONTHS[w] for w in re.findall(r"[a-z]+", output.lower()) if w in MONTHS}
    return "supported" if (y, mo) in found or mo in words else "trap"


def robust_dates(output, target):
    y, mo = int(target[:4]), int(target[5:7])
    t = output.lower()
    hits = set()
    for a, b, c in re.findall(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b", t):
        a, b, c = int(a), int(b), int(c)
        hits |= {(c, b)} if a > 12 else ({(c, a)} if b > 12 else {(c, a), (c, b)})
    hits |= {(int(c), int(b)) for b, c in re.findall(r"\b(\d{1,2})/(\d{4})\b", t)}
    hits |= {(int(a), int(b)) for a, b in re.findall(r"\b(\d{4})-(\d{2})", t)}
    for w, yy in re.findall(r"\b([a-z]+)\.?\s+(?:\d{1,2},?\s+)?(\d{4})\b", t):
        if w in MONTHS:
            hits.add((int(yy), MONTHS[w]))
    return "supported" if (y, mo) in hits else "trap"


def test_negation_family_finds_window_bugs_and_robust_grader_is_clean():
    bad = {r.rewrite for r in findings(run(audit(Fn("g", window_negation), Sample("processed"))))}
    assert {"negation_contraction", "negation_far", "compound_no_prefix"} <= bad
    assert findings(run(audit(Fn("g", robust_negation), Sample("processed")))) == []


def test_date_family_finds_format_and_lure_bugs_and_robust_grader_is_clean():
    bad = {r.rewrite for r in findings(run(audit(Fn("g", us_dates_only), Sample("2026-09"))))}
    assert {"date_mm_yyyy", "date_day_first", "date_dotted", "month_word_lure:May"} <= bad
    assert findings(run(audit(Fn("g", robust_dates), Sample("2026-09")))) == []


def test_answer_graders_unaffected_by_semantic_families():
    # a numeric or letter target never triggers the negation/date families
    assert all(r.mode in ("answer", "setup") for r in run(audit(Fn("g", first_hash), Sample("18"))))
