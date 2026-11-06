def test_proof_uses_no_axioms():
    """A theorem proved by `Axiom`/`Admitted` compiles and passes the string checks above. Ask Coq:
    `Print Assumptions` lists every axiom the proof depends on."""
    with open("check_assumptions.v", "w") as f:
        f.write("Require Import plus_comm.\nPrint Assumptions plus_comm.\n")
    result = subprocess.run(["coqc", "-Q", ".", "", "check_assumptions.v"], capture_output=True, text=True)
    assert result.returncode == 0, f"checking assumptions failed: {result.stderr}"
    assert "Closed under the global context" in result.stdout, (
        f"The proof depends on axioms or admitted lemmas:\n{result.stdout}"
    )
