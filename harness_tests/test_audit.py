from kernelmind.audit import mutants

SCRIPT = """#!/bin/bash
pip install requests==2.31
mkdir -p out
cat > run.py << 'EOF'
if n <= 3 and ok == True:
    print(n + 10)
EOF
python3 run.py > out/result.txt
"""


def test_mutants_are_single_site_and_deterministic():
    a, b = mutants(SCRIPT, "seed"), mutants(SCRIPT, "seed")
    assert a == b and a
    for name, text in a:
        assert text != SCRIPT, name


def test_mutants_skip_installs_and_heredoc_markers():
    for name, text in mutants(SCRIPT, "s", n=50):
        assert "requests==2.31" in text, name  # dependency pins are never mutated
        assert "<< 'EOF'" in text and "\nEOF\n" in text, name  # heredoc structure stays intact
        if "delete-step" in name:
            assert "if n" in text and "print(" in text, name  # deletions only at shell level


def test_mutation_kinds_present():
    kinds = {n.split("-")[2] for n, _ in mutants(SCRIPT, "s", n=50)}
    assert {"number", "compare", "boolean", "delete"} <= kinds


def test_shell_redirects_are_not_comparisons():
    for name, text in mutants(SCRIPT, "s", n=50):
        assert "cat > run.py" in text and "> out/result.txt" in text or "delete-step" in name, name


def test_mutants_spread_across_lines():
    lines = [n.rsplit("-L", 1)[1] for n, _ in mutants(SCRIPT, "s", n=4)]
    assert len(set(lines)) == len(lines)


def test_classify_keeps_kind_and_summary_counts(tmp_path):
    from kernelmind.audit import classify, summary_rows
    from kernelmind.validate import Check
    from kernelmind.verify import Verdict
    meta = {"near-1-partial": {"source": "llm", "category": "partial"}, "alt-1": {"source": "llm"},
            "mut-1-number-L1": {"source": "mutant"}}
    checks = [Check("t", "near-1-partial", "control", "fail", Verdict(True), False, "", 0),
              Check("t", "alt-1", "alternative", "pass", Verdict(True), True, "", 0),
              Check("t", "mut-1-number-L1", "control", "fail", Verdict(False), True, "", 0)]
    r = classify(checks, meta)
    assert [c["kind"] for c in r["candidates"]] == ["control", "alternative", "control"]
    row = summary_rows([{"task": "t", **r}])[2]
    assert "| 1/1 | 0/1 | 1/1 | near-1-partial |" in row
