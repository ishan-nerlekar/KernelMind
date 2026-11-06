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
    r = classify(checks + [Check("t", "reference", "reference", "pass", Verdict(True), True, "", 0),
                           Check("t", "starter", "starter", "fail", Verdict(True), False, "", 0)], meta)
    assert [c["kind"] for c in r["candidates"]] == ["control", "alternative", "control"]
    assert r["baseline_ok"] and r["starter_passes"]
    row = summary_rows([{"task": "t", **r}])[2]
    assert "| 1/1 | 0/1 | 1/1 | starter (doing nothing passes), near-1-partial |" in row


PATCH = """--- a/x.go
+++ b/x.go
@@ -1,3 +1,3 @@
 // keep 1
-if n >= 10 {
+if n > 10 && ok == true {
+	// limit 5
 	return 3
"""


def test_patch_mutants_touch_only_added_code_lines():
    out = mutants(PATCH, "s", n=20, patch=True)
    assert out
    for name, text in out:
        before, after = PATCH.splitlines(), text.splitlines()
        changed = [i for i, (x, y) in enumerate(zip(before, after)) if x != y]
        assert changed == [5], (name, changed)  # only the added code line, never context or the added comment
        assert "delete-step" not in name


def test_requirement_and_repeat_modes_share_requirements_and_budget(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from kernelmind import audit
    root = tmp_path / "t"
    (root / "solution").mkdir(parents=True)
    (root / "solution" / "solve.sh").write_text("#!/bin/bash\necho ok\n")
    task = SimpleNamespace(id="t", root=root, instruction="do things")
    calls = []

    def fake(model, prompt, max_tokens=16000):
        calls.append(prompt)
        if prompt.startswith("Below is the instruction"):
            return {"requirements": [f"r{i}" for i in range(6)]}, 0.01
        return {"near_misses": [{"violates": "x", "solve_sh": "#!/bin/bash"}] * 9}, 0.0  # over-long replies are cut

    monkeypatch.setattr(audit, "complete", fake)
    req, _ = audit.llm_candidates(task, "m", 1, 0, "requirement", tmp_path / "cache")
    rep, _ = audit.llm_candidates(task, "m", 1, 0, "repeat", tmp_path / "cache")
    assert len(calls) == 1 + 2 + 2  # requirements extracted once (cached), then 2 chunks per arm
    assert "1. r0" in calls[1] and "2. r5" in calls[2]
    assert len(req["near_misses"]) == len(rep["near_misses"]) == 6  # one per requirement in both arms
    assert all(nm["category"] == "req" for nm in req["near_misses"])
