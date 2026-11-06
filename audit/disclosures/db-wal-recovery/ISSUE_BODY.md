**What the instruction requires**
> 1. Fix the WAL file so SQLite can read it
> 2. Extract ALL data from the database (including WAL changes)
> 3. Create a JSON file in /app/recovered.json

**What passes today**
`near-4-symptom/solve.sh` (below) decrypts a scratch copy, writes the correct `recovered.json`, and leaves `/app/main.db-wal` encrypted, so SQLite on `/app/main.db` still sees 5 records. It passes.

**Why the tests miss it**
All tests read `/app/recovered.json`; none opens `/app/main.db`.

**Suggested fix** (below): open `/app/main.db` read-only with `sqlite3` and require 11 rows in `items`.
Checked locally: the reference solution passes; near-4 fails with "SQLite still sees 5 records".

Confirmed with Harbor 0.25 (`harbor trial start -a oracle`): the reference and each solution below score reward 1.0.

**Reproduce** (Harbor oracle agent with the solution swapped in):
```bash
cp -R db-wal-recovery /tmp/db-wal-recovery-check
# put one of the solve.sh scripts below in /tmp/db-wal-recovery-check/solution/solve.sh, then:
harbor trial start -p /tmp/db-wal-recovery-check -a oracle
```

<details><summary><code>near-4-symptom/solve.sh</code> (passes the current tests)</summary>

```bash
#!/bin/bash
set -e
cd /app
mkdir -p /tmp/scratch
cp /app/main.db /tmp/scratch/main.db
# Decrypt only the scratch copy of the WAL
python3 - <<'EOF'
with open('/app/main.db-wal', 'rb') as f:
    data = f.read()
with open('/tmp/scratch/main.db-wal', 'wb') as f:
    f.write(bytes(b ^ 0x42 for b in data))
EOF
python3 - <<'EOF'
import sqlite3, json
conn = sqlite3.connect('/tmp/scratch/main.db')
rows = conn.execute('SELECT id, name, value FROM items ORDER BY id').fetchall()
conn.close()
data = [{"id": r[0], "name": r[1], "value": r[2]} for r in rows]
with open('/app/recovered.json', 'w') as f:
    json.dump(data, f, indent=2)
EOF
```
</details>

<details><summary>Tests to add to `tests/test_outputs.py`</summary>

```python
def test_wal_fixed_in_place():
    """Instruction step 1: 'Fix the WAL file so SQLite can read it.' Only recovered.json is checked
    above, so leaving /app/main.db-wal encrypted still passes. Open the database as SQLite would."""
    import sqlite3
    con = sqlite3.connect("file:/app/main.db?mode=ro", uri=True)
    (n,) = con.execute("SELECT COUNT(*) FROM items").fetchone()
    assert n == 11, f"SQLite still sees {n} records in /app/main.db; the WAL was not fixed"
```
</details>


_Found while auditing Terminal-Bench 2.0 verifiers with near-miss solutions (commit `2fd12b8`). Happy to turn the suggested test change into a PR._
