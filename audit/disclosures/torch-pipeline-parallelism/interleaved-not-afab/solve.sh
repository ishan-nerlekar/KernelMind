#!/bin/bash
cat > /app/pipeline_parallel.py <<'EOF'
import torch, torch.distributed as dist, torch.nn as nn, torch.nn.functional as F
def train_step_pipeline_afab(model, inputs, targets, device, dtype):
    rank=dist.get_rank(); ws=dist.get_world_size()
    bm=model.model; n=len(bm.layers)
    per=[n//ws+(1 if i<n%ws else 0) for i in range(ws)]
    s=sum(per[:rank]); bm.layers=nn.ModuleList(bm.layers[s:s+per[rank]])
    if rank!=ws-1: bm.norm=nn.Identity(); model.lm_head=nn.Identity()
    if rank!=0: bm.embed_tokens=nn.Identity()
    mb,sl=inputs[0].shape; shp=(mb,sl,model.config.hidden_size); k=len(inputs)
    for i in range(k):
        if rank==0: x=inputs[i].to(device)
        else:
            x=torch.empty(shp,device=device,dtype=dtype); dist.recv(x,rank-1); x.requires_grad_(True)
        out=model(x)[0]
        if rank!=ws-1: dist.send(out.detach().contiguous(),rank+1)
        if rank==ws-1:
            loss=F.cross_entropy(out.view(-1,out.size(-1)),targets[i].to(device).view(-1),ignore_index=-100)/k
            loss.backward()
        else:
            g=torch.empty(shp,device=device,dtype=dtype); dist.recv(g,rank+1); out.backward(g)
        if rank!=0: dist.send(x.grad.contiguous(),rank-1)
EOF
