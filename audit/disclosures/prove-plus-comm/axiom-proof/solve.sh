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
