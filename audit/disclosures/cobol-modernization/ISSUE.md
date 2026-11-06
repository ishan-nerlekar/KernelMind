**Title:** cobol-modernization: every graded transaction is a valid sale, so a port that skips the COBOL validation passes

**What the instruction requires**
> create a new Python script located at /app/program.py, which performs the exact same operations as the COBOL program.

`program.cbl` only processes a sale when buyer, seller and book exist and the seller owns the book (`IF BOOK-OWNER = WS-SELLER-ID`, lines 76–77 and 112).

**What passes today**
`near-2-edge-case/solve.sh` is a port without the ownership check: it transfers money and the book even when the seller doesn't own it. It passes.

**Why the tests miss it**
`test_program_output` resets the data so that `B003` belongs to `U003`, then runs three sales that are all valid at the time they run. The rejection path is never exercised.

**Suggested fix** (`test_fix_addition.py`): from the same initial state, run `U002U001B0030000000010` (U001 doesn't own B003) and require all three .DAT files unchanged. That is GnuCOBOL 3.1's behavior for `program.cbl`; we checked that the same build reproduces the existing test's expected files.
Checked locally: the reference `program.py` passes; near-2 fails.
