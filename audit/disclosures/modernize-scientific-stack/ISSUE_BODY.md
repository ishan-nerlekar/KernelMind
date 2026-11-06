**What the instruction requires**
> - `/app/climate_analyzer/analyze_climate.py` - Original Python 2 script (DO NOT MODIFY)

> - Include numpy, pandas, and at least one of: matplotlib, scipy
> - Specify version constraints using >=, ==, or ~=

**What passes today**
- `near-1-partial/solve.sh` (below) writes `requirements.txt` with bare `numpy`, `pandas`, `matplotlib` (no constraints). It passes.
- `near-4-over-broad/solve.sh` (below) inserts a line into `/app/climate_analyzer/analyze_climate.py`. It passes.

**Why the tests miss it**
`test_dependency_file_exists` only checks that a dependency file exists; nothing checks its contents or the legacy script.

**Suggested fix** (below): require a version specifier for numpy and pandas and the presence of matplotlib or scipy; compare the legacy script's SHA-256 with the shipped file (`112e2626…65dd0`).
Checked locally: the reference solution passes; near-1 fails the first new test and near-4 the second.

**Reproduce** (Harbor oracle agent with the solution swapped in):
```bash
cp -R modernize-scientific-stack /tmp/modernize-scientific-stack-check
# put one of the solve.sh scripts below in /tmp/modernize-scientific-stack-check/solution/solve.sh, then:
harbor trial start -p /tmp/modernize-scientific-stack-check -a oracle
```

<details><summary><code>near-1-partial/solve.sh</code> (passes the current tests)</summary>

```bash
#!/bin/bash
set -e

# requirements.txt with bare package names and no version constraints
cat > /app/requirements.txt << 'EOF'
numpy
pandas
matplotlib
EOF

cat > /app/analyze_climate_modern.py << 'EOF'
#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
from configparser import ConfigParser

csv_path = Path('/app/climate_analyzer/sample_data/climate_data.csv')
df = pd.read_csv(csv_path, encoding='utf-8')
config_path = Path('/app/climate_analyzer/config.ini')
if config_path.exists():
    config = ConfigParser()
    config.read(config_path, encoding='utf-8')
for station_id in df['station_id'].unique():
    station_data = df[df['station_id'] == station_id]
    mean_temp = station_data['temperature'].mean()
    print(f'Station {station_id} mean temperature: {mean_temp:.1f}°C')
EOF

python3 /app/analyze_climate_modern.py
```
</details>

<details><summary><code>near-4-over-broad/solve.sh</code> (passes the current tests)</summary>

```bash
#!/bin/bash
set -e

# Tidy the legacy script in place while we are here
sed -i '1i # modernized: see analyze_climate_modern.py' /app/climate_analyzer/analyze_climate.py

cat > /app/requirements.txt << 'EOF'
numpy>=1.21.0
pandas>=1.3.0
matplotlib>=3.5.0
scipy>=1.7.0
EOF

cat > /app/analyze_climate_modern.py << 'EOF'
#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
from configparser import ConfigParser

csv_path = Path('/app/climate_analyzer/sample_data/climate_data.csv')
df = pd.read_csv(csv_path, encoding='utf-8')
config_path = Path('/app/climate_analyzer/config.ini')
if config_path.exists():
    config = ConfigParser()
    config.read(config_path, encoding='utf-8')
for station_id in df['station_id'].unique():
    station_data = df[df['station_id'] == station_id]
    mean_temp = station_data['temperature'].mean()
    print(f'Station {station_id} mean temperature: {mean_temp:.1f}°C')
EOF

python3 /app/analyze_climate_modern.py
```
</details>

<details><summary>Tests to add to `tests/test_outputs.py`</summary>

```python
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
```
</details>


_Found while auditing Terminal-Bench 2.0 verifiers with near-miss solutions (commit `2fd12b8`). Happy to turn the suggested test change into a PR._
