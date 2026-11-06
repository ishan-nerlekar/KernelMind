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
