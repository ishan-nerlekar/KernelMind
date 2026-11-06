**Title:** modernize-scientific-stack: the "DO NOT MODIFY" script and the version-constraint requirement are never checked

**What the instruction requires**
> - `/app/climate_analyzer/analyze_climate.py` - Original Python 2 script (DO NOT MODIFY)

> - Include numpy, pandas, and at least one of: matplotlib, scipy
> - Specify version constraints using >=, ==, or ~=

**What passes today**
- `near-1-partial/solve.sh` writes `requirements.txt` with bare `numpy`, `pandas`, `matplotlib` (no constraints). It passes.
- `near-4-over-broad/solve.sh` inserts a line into `/app/climate_analyzer/analyze_climate.py`. It passes.

**Why the tests miss it**
`test_dependency_file_exists` only checks that a dependency file exists; nothing checks its contents or the legacy script.

**Suggested fix** (`test_fix_addition.py`): require a version specifier for numpy and pandas and the presence of matplotlib or scipy; compare the legacy script's SHA-256 with the shipped file (`112e2626…65dd0`).
Checked locally: the reference solution passes; near-1 fails the first new test and near-4 the second.
