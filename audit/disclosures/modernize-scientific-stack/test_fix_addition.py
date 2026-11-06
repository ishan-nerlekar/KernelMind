def test_dependency_versions_constrained():
    """'Specify version constraints using >=, ==, or ~=' and 'Include numpy, pandas, and at least one
    of: matplotlib, scipy' are stated requirements; above, only the file's existence is checked."""
    import re
    req = Path("/app/requirements.txt")
    text = req.read_text() if req.exists() else Path("/app/pyproject.toml").read_text()
    for pkg in ("numpy", "pandas"):
        assert re.search(rf"\b{pkg}\s*(>=|==|~=)\s*\d", text, re.I), f"{pkg} has no version constraint"
    assert re.search(r"\b(matplotlib|scipy)\b", text, re.I), "needs matplotlib or scipy"


def test_legacy_script_untouched():
    """'/app/climate_analyzer/analyze_climate.py - Original Python 2 script (DO NOT MODIFY)'."""
    import hashlib
    data = Path("/app/climate_analyzer/analyze_climate.py").read_bytes()
    assert hashlib.sha256(data).hexdigest() == "112e26265c2b7a579403c9690f5d58cbc1bf59468bfcb7496e4fdbec9a565dd0", "the legacy script was modified"
