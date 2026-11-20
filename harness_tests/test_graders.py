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
