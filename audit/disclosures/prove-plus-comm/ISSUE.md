**Title:** prove-plus-comm: an `Axiom` stating the theorem, or `Admitted.` with `Qed.` in a comment, passes as a proof

**What the instruction requires**
> Add the missing steps to complete the proof ... The proof should be completed using Coq's tactics

**What passes today**
- `axiom-proof/solve.sh` declares `Axiom plus_comm_axiom : forall n m : nat, n + m = m + n.` and proves the theorem with `apply plus_comm_axiom.` It passes.
- `admitted-in-comment/solve.sh` ends the proof with `Admitted. (* Qed. *)`. It passes: the `"admit" not in content` check is case-sensitive, and `"Qed." in content` matches the comment.

**Why the tests miss it**
The tests check strings in `plus_comm.v` and that it compiles; nothing asks Coq whether the proof depends on axioms.

**Suggested fix** (`test_fix_addition.py`): compile a two-line file `Require Import plus_comm. Print Assumptions plus_comm.` and require `Closed under the global context`.
Checked locally with Coq 8.18: the reference passes; both solutions above fail.
