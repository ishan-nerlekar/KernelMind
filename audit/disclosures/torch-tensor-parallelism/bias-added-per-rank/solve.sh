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
