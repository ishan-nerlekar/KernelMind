**What the instruction requires**
> Add the missing steps to complete the proof ... The proof should be completed using Coq's tactics

**What passes today**
- `axiom-proof/solve.sh` (below) declares `Axiom plus_comm_axiom : forall n m : nat, n + m = m + n.` and proves the theorem with `apply plus_comm_axiom.` It passes.
- `admitted-in-comment/solve.sh` (below) ends the proof with `Admitted. (* Qed. *)`. It passes: the `"admit" not in content` check is case-sensitive, and `"Qed." in content` matches the comment.

**Why the tests miss it**
The tests check strings in `plus_comm.v` and that it compiles; nothing asks Coq whether the proof depends on axioms.

**Suggested fix** (below): compile a two-line file `Require Import plus_comm. Print Assumptions plus_comm.` and require `Closed under the global context`.
Checked locally with Coq 8.18: the reference passes; both solutions above fail.

**Reproduce** (Harbor oracle agent with the solution swapped in):
```bash
cp -R prove-plus-comm /tmp/prove-plus-comm-check
# put one of the solve.sh scripts below in /tmp/prove-plus-comm-check/solution/solve.sh, then:
harbor trial start -p /tmp/prove-plus-comm-check -a oracle
```

<details><summary><code>admitted-in-comment/solve.sh</code> (passes the current tests)</summary>

```bash
#!/bin/bash
set -e
cat > plus_comm.v <<'EOF'
Require Import Arith.

Theorem plus_comm : forall n m : nat,
  n + m = m + n.
Proof.
  intros n m.
Admitted. (* Qed. *)
EOF
coqc plus_comm.v
```
</details>

<details><summary><code>axiom-proof/solve.sh</code> (passes the current tests)</summary>

```bash
#!/bin/bash
set -e
cat > plus_comm.v <<'EOF'
Require Import Arith.

Axiom plus_comm_axiom : forall n m : nat, n + m = m + n.

Theorem plus_comm : forall n m : nat,
  n + m = m + n.
Proof.
  intros n m.
  apply plus_comm_axiom.
Qed.
EOF
coqc plus_comm.v
```
</details>

<details><summary>Tests to add to `tests/test_outputs.py`</summary>

```python
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
```
</details>


_Found while auditing Terminal-Bench 2.0 verifiers with near-miss solutions (commit `2fd12b8`). Happy to turn the suggested test change into a PR._
