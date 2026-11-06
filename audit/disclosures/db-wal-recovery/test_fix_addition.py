def test_wal_fixed_in_place():
    """Instruction step 1: 'Fix the WAL file so SQLite can read it.' Only recovered.json is checked
    above, so leaving /app/main.db-wal encrypted still passes. Open the database as SQLite would."""
    import sqlite3
    con = sqlite3.connect("file:/app/main.db?mode=ro", uri=True)
    (n,) = con.execute("SELECT COUNT(*) FROM items").fetchone()
    assert n == 11, f"SQLite still sees {n} records in /app/main.db; the WAL was not fixed"
