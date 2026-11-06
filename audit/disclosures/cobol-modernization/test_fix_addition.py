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
