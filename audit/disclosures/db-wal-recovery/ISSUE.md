**Title:** db-wal-recovery: step 1 ("Fix the WAL file so SQLite can read it") is never checked

**What the instruction requires**
> 1. Fix the WAL file so SQLite can read it
> 2. Extract ALL data from the database (including WAL changes)
> 3. Create a JSON file in /app/recovered.json

**What passes today**
`near-4-symptom/solve.sh` decrypts a scratch copy, writes the correct `recovered.json`, and leaves `/app/main.db-wal` encrypted, so SQLite on `/app/main.db` still sees 5 records. It passes.

**Why the tests miss it**
All tests read `/app/recovered.json`; none opens `/app/main.db`.

**Suggested fix** (`test_fix_addition.py`): open `/app/main.db` read-only with `sqlite3` and require 11 rows in `items`.
Checked locally: the reference solution passes; near-4 fails with "SQLite still sees 5 records".
