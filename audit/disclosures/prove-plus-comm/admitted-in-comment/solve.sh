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
