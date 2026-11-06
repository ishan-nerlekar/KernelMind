**What the instruction requires**
> RowParallelLinear splits the weight matrix by rows; the partial outputs should be summed together as if using all_reduce; the bias remains full on each rank.

**What passes today**
`bias-added-per-rank/solve.sh` (below) adds the full bias to each rank's partial output *before* the all_reduce, so after the reduction the output contains the bias `world_size` times. It passes for world sizes 1, 2 and 4.

**Why the tests miss it**
The instruction says to initialize the bias to zero, and the tests check the output while it is still zero, so `world_size × 0 = 0`. The bias gradient is still correct for this bug, so the backward check doesn't catch it either. The same blind spot applies to ColumnParallelLinear's bias in the forward check.

**Suggested fix** (below): after checking that the bias was initialized to zero, give the reference and parallel biases the same non-zero values, then run the existing forward and backward checks.
{{HARBOR_FIX_CHECK}}

**Reproduce** (Harbor oracle agent with the solution swapped in):
```bash
cp -R torch-tensor-parallelism /tmp/torch-tensor-parallelism-check
# put one of the solve.sh scripts below in /tmp/torch-tensor-parallelism-check/solution/solve.sh, then:
harbor trial start -p /tmp/torch-tensor-parallelism-check -a oracle
```

<details><summary><code>bias-added-per-rank/solve.sh</code> (passes the current tests)</summary>

```bash
#!/bin/bash
cat << 'EOF' > /app/parallel_linear.py
import torch
import torch.nn.functional as F
import torch.distributed as dist

class _Gather(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x):
        ws = dist.get_world_size()
        if ws == 1:
            return x
        x = x.contiguous()
        l = [torch.empty_like(x) for _ in range(ws)]
        dist.all_gather(l, x)
        return torch.cat(l, -1)
    @staticmethod
    def backward(ctx, g):
        ws = dist.get_world_size(); r = dist.get_rank()
        if ws == 1:
            return g
        n = g.size(-1) // ws
        return g[..., r*n:(r+1)*n].clone()

class _AR(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x):
        x = x.clone()
        if dist.get_world_size() > 1:
            dist.all_reduce(x)
        return x
    @staticmethod
    def backward(ctx, g):
        return g

class ColumnParallelLinear(torch.nn.Module):
    def __init__(self, in_features, out_features, bias, master_weight):
        super().__init__()
        ws = dist.get_world_size(); r = dist.get_rank()
        n = out_features // ws
        self.weight = torch.nn.Parameter(master_weight[r*n:(r+1)*n].clone().detach())
        if bias:
            self.bias = torch.nn.Parameter(torch.zeros(n))
        else:
            self.register_parameter('bias', None)
    def forward(self, x):
        return _Gather.apply(F.linear(x, self.weight, self.bias))

class RowParallelLinear(torch.nn.Module):
    def __init__(self, in_features, out_features, bias, master_weight):
        super().__init__()
        ws = dist.get_world_size(); r = dist.get_rank()
        n = in_features // ws
        self.weight = torch.nn.Parameter(master_weight[:, r*n:(r+1)*n].clone().detach())
        if bias:
            self.bias = torch.nn.Parameter(torch.zeros(out_features))
        else:
            self.register_parameter('bias', None)
    def forward(self, x):
        # BUG: bias added before all_reduce -> counted world_size times
        return _AR.apply(F.linear(x, self.weight, self.bias))
EOF
```
</details>

<details><summary>Patch to <code>tests/test_outputs.py</code></summary>

```diff
--- a/torch-tensor-parallelism/tests/test_outputs.py	2026-11-06 17:34:37.752768843 +0000
+++ b/torch-tensor-parallelism/tests/test_outputs.py	2026-11-06 17:34:37.786657376 +0000
@@ -78,6 +78,10 @@
         assert torch.allclose(parallel_layer.bias, expected_bias_slice, atol=1e-5), (
             f"ColumnParallelLinear bias mismatch on rank {rank}."
         )
+        # A zero bias hides a bias applied the wrong number of times; give it values before the forward check.
+        with torch.no_grad():
+            reference_layer.bias.copy_(torch.linspace(-1, 1, out_features))
+            parallel_layer.bias.copy_(reference_layer.bias[start_idx:end_idx])
 
     # Test forward pass
     input_tensor = torch.randn(batch_size, in_features)
@@ -146,6 +150,10 @@
         assert torch.allclose(parallel_layer.bias, reference_layer.bias, atol=1e-5), (
             f"RowParallelLinear bias mismatch on rank {rank}."
         )
+        # A zero bias hides a bias added once per rank (before the all_reduce); give it values first.
+        with torch.no_grad():
+            reference_layer.bias.copy_(torch.linspace(-1, 1, out_features))
+            parallel_layer.bias.copy_(reference_layer.bias)
 
     # Test forward pass
     # Note: In a row parallel setup, the input would be scattered to each rank.
```
</details>
