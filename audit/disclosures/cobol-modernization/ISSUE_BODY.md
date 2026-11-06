**What the instruction requires**
> create a new Python script located at /app/program.py, which performs the exact same operations as the COBOL program.

`program.cbl` only processes a sale when buyer, seller and book exist and the seller owns the book (`IF BOOK-OWNER = WS-SELLER-ID`, lines 76–77 and 112).

**What passes today**
`near-2-edge-case/solve.sh` (below) is a port without the ownership check: it transfers money and the book even when the seller doesn't own it. It passes.

**Why the tests miss it**
`test_program_output` resets the data so that `B003` belongs to `U003`, then runs three sales that are all valid at the time they run. The rejection path is never exercised.

**Suggested fix** (below): from the same initial state, run `U002U001B0030000000010` (U001 doesn't own B003) and require all three .DAT files unchanged. That is GnuCOBOL 3.1's behavior for `program.cbl`; we checked that the same build reproduces the existing test's expected files.
Checked locally: the reference `program.py` passes; near-2 fails.

**Reproduce** (Harbor oracle agent with the solution swapped in):
```bash
cp -R cobol-modernization /tmp/cobol-modernization-check
# put one of the solve.sh scripts below in /tmp/cobol-modernization-check/solution/solve.sh, then:
harbor trial start -p /tmp/cobol-modernization-check -a oracle
```

<details><summary><code>near-2-edge-case/solve.sh</code> (passes the current tests)</summary>

```bash
#!/bin/bash
set -e
cat > /app/program.py << 'EOF'
import os
os.chdir('/app')
inp = open('src/INPUT.DAT').read().strip()
buyer, seller, book = inp[0:4], inp[4:8], inp[8:12]
amount = int(inp[12:])
data = open('data/ACCOUNTS.DAT').read()
recs = [data[i:i+34] for i in range(0, len(data), 34)]
ids = [r[:4] for r in recs]
books = open('data/BOOKS.DAT').read()
brecs = [books[i:i+28] for i in range(0, len(books), 28)]
ok = buyer in ids and seller in ids and any(b[:4] == book for b in brecs)
if ok:
    out = []
    for r in recs:
        bal = int(r[24:34])
        if r[:4] == buyer:
            bal -= amount
        elif r[:4] == seller:
            bal += amount
        out.append(f'{r[:24]}{bal:010d}')
    open('data/ACCOUNTS.DAT', 'w').write(''.join(out))
    bout = []
    for b in brecs:
        if b[:4] == book:
            b = b[:24] + buyer
        bout.append(b)
    open('data/BOOKS.DAT', 'w').write(''.join(bout))
    tx = open('data/TRANSACTIONS.DAT').read()
    open('data/TRANSACTIONS.DAT', 'w').write(tx + f'{book}{amount:010d}{seller}{buyer}')
EOF
```
</details>

<details><summary>Tests to add to `tests/test_outputs.py`</summary>

```python
def test_rejected_sale_leaves_files_unchanged():
    """All three transactions above are valid sales, so the COBOL program's validation (buyer, seller
    and book must exist, and the seller must own the book) is never exercised; a port that skips it
    passes. Ground truth from GnuCOBOL 3.1: this sale is rejected and no file changes."""
    data_dir = Path("/app/data")
    initial = {
        "ACCOUNTS.DAT": "U001John Doe            0000001000U002Jane Smith          0000002000U003Bob Wilson          0000001500",
        "BOOKS.DAT": "B001Python Basics       U001B002COBOL Guide         U002B003Java Tutorial       U003",
        "TRANSACTIONS.DAT": "",
    }
    for name, text in initial.items():
        (data_dir / name).write_text(text)
    Path("/app/src/INPUT.DAT").write_text("U002U001B0030000000010")  # U001 does not own B003
    result = subprocess.run(["python", "/app/program.py"], capture_output=True, text=True)
    assert result.returncode == 0, "Command failed"
    for name, text in initial.items():
        assert (data_dir / name).read_text() == text, f"{name} changed although the sale is invalid"
```
</details>


_Found while auditing Terminal-Bench 2.0 verifiers with near-miss solutions (commit `2fd12b8`). Happy to turn the suggested test change into a PR._
