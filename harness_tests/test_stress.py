from kernelmind.stress import UNSCORED, Case, Probe, answer_cases, compare_known, judge_cases, run


def test_answer_cases_keep_or_break_meaning():
    cases = {c.rewrite: c for c in answer_cases("Work.\nANSWER: {a}", "18", "126", numeric=True)}
    assert cases["bold_answer"].text == "Work.\nANSWER: **18**" and cases["bold_answer"].expect == "same"
    assert cases["bold_label"].text == "Work.\n**ANSWER:** 18"
    assert cases["hedge"].expect == "wrong" and "126" in cases["hedge"].text
    assert cases["superseded_draft_bold_line"].text.endswith("**ANSWER: 126**")
    assert "upper_case" not in cases  # "18".upper() is unchanged, so no case is generated


def test_answer_cases_for_letters_skip_case_changes():
    names = {c.rewrite for c in answer_cases("ANSWER: {a}", "C", "B", letters=True)}
    assert not names & {"upper_case", "title_case", "boxed"}


def test_judge_cases():
    cases = {c.rewrite: c for c in judge_cases('{"label": "{v}"}', "unsafe")}
    assert cases["token_capitalised"].text == '{"label": "Unsafe"}'
    assert cases["empty_reply"].expect == UNSCORED
    hdr = {c.rewrite: c.text for c in judge_cases("#scores\n1.b {v}", "5", numeric=True, header="#scores")}
    assert hdr["header_markdown"].startswith("## Scores") and hdr["header_capitalised"].startswith("#Scores")


def _probe(grade, cases, base="ANSWER: 18", verdict="C"):
    async def g(text):
        return grade(text)
    return Probe("fake", "answer", g, base, verdict, cases)


def test_outcomes():
    strict = lambda t: "C" if t == "ANSWER: 18" else ("I" if t else UNSCORED)  # noqa: E731
    res = run([_probe(strict, [Case("bold", "ANSWER: **18**", "same"), Case("near", "ANSWER: 17", "wrong"),
                               Case("empty", "", "same"), Case("empty2", "", UNSCORED)])])
    assert [r.outcome for r in res] == ["FLIP", "ok", "DROP", "ok"]


def test_setup_failure_and_errors():
    def boom(t):
        raise ValueError("x")
    assert run([_probe(lambda t: "I", [])])[0].outcome == "SETUP"
    res = run([_probe(lambda t: boom(t) if "**" in t else "C", [Case("bold", "**18**", "same")])])
    assert res[0].outcome == "ERROR"


def test_compare_known():
    res = run([_probe(lambda t: "C" if t == "ANSWER: 18" else "I", [Case("bold", "x", "same"), Case("ok", "ANSWER: 18", "same")])])
    out = compare_known(res, {"fake": {"bold", "period"}})
    assert out["rediscovered"] == 1 and out["missed"] == [("fake", "period")] and out["new"] == []


def test_stress_map(tmp_path):
    from kernelmind.stress_map import exposure, scan
    ev = tmp_path / "toy"
    ev.mkdir()
    (ev / "toy.py").write_text(
        "import re\nfrom inspect_ai.scorer import match, choice, scorer\n"
        "def task():\n    return dict(scorer=[match(numeric=True), choice()])\n"
        "@scorer(metrics=[])\ndef toy_scorer():\n    return re.search('x', 'y')\n")
    (tmp_path / "utils").mkdir()
    [e] = scan(tmp_path)
    assert e.name == "toy" and e.builtins == ["choice()", "match(numeric=True)"]
    assert e.custom == ["toy_scorer"] and e.parse_calls == 1
    assert exposure([e])["match(numeric=True)"] == ["toy"]
