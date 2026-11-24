"""Fit the two circuit families on calibration words; test on untouched words."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time
from application import Aig,DESIGNS,check_equivalent,replace,sample,select,signal
from audit import literals_cached
from correlated import Optimizer,path_lengths,transition_panels
from run import digest,pin
from synthesize import Circuit


def patterns(name,count,role,panels,width):
    rngs=[random.Random(f"puncture-transfer/v1/{name}/{role}/{j}") for j in range(panels)]
    values=[]
    field=(1<<width)-1
    for _ in range(count):
        lo=hi=0
        for j,rng in enumerate(rngs):
            pair=rng.getrandbits(2*width)
            lo|=(pair&field)<<(j*width)
            hi|=(pair>>width)<<(j*width)
        values.append(lo|(hi<<(width*panels)))
    return values


def original_endpoint(net,leaves,cone,root):
    n=len(leaves)
    c=Circuit(n)
    local={v:(i,0) for i,v in enumerate(leaves)}
    for g in sorted(cone):
        wires=[]
        for lit in net.gates[g-net.inputs-1]:
            i,neg=local[lit//2]
            wires.append((i,neg^(lit&1)))
        local[g]=c.gate(*wires,8)
    return dict(gates=c.gates,complement=local[root][1],gate_count=len(c.gates))


def arrivals(net,choices,defaults):
    levels=[0]*(net.inputs+1)
    for g,(a,b) in enumerate(net.gates,net.inputs+1):
        if g in choices:
            leaves=choices[g][0]
            distances=path_lengths(len(leaves),defaults[g])
            levels.append(max(levels[i]+d for i,d in zip(leaves,distances)))
        else:
            levels.append(1+max(levels[a//2],levels[b//2]))
    return levels


def verify_truth(n,t,ep):
    values=list(literals_cached(n))
    mask=(1<<(1<<n))-1
    for a,b,op in ep["gates"]:
        x,y=values[a],values[b]
        v={2:x&~y,4:y&~x,8:x&y,14:x|y,6:x^y}[op]
        values.append(v)
    assert (values[-1]^(mask if ep["complement"] else 0))==t


def choose(net,choices,claimed,defaults,training,family):
    reference=arrivals(net,choices,defaults)
    max_depth=max(reference[o//2] for o in net.outputs)
    required=[max_depth+net.inputs+len(net.gates)+1]*len(reference)
    for out in net.outputs:
        required[out//2]=max_depth
    selection={}
    changed=0
    training_savings=[0]*4
    for g in reversed(range(net.inputs+1,len(reference))):
        if g in choices:
            leaves,_,answer,_=choices[g]
            t=int(answer["truth"],16)
            values=[training[v] for v in leaves]
            old=defaults[g]
            candidate=Optimizer(t,values,2048,[reference[i] for i in leaves]).endpoint(family,required[g])
            ep=old
            if candidate:
                cost,next_ep=candidate
                new_scores=transition_panels(values,next_ep,512,4)
                assert cost==sum(new_scores)
                old_scores=transition_panels(values,old,512,4)
                if all(a<b for a,b in zip(new_scores,old_scores)):
                    ep=next_ep
                    changed+=1
                    for j in range(4):
                        training_savings[j]+=old_scores[j]-new_scores[j]
            selection[g]=ep
            verify_truth(len(leaves),t,ep)
            distances=path_lengths(len(leaves),ep)
            for leaf,delay in zip(leaves,distances):
                assert reference[leaf]+delay<=required[g]
                required[leaf]=min(required[leaf],required[g]-delay)
        elif g not in claimed:
            for lit in net.gates[g-net.inputs-1]:
                required[lit//2]=min(required[lit//2],required[g]-1)
    return selection,changed,training_savings


def packed_network(net,pis,bits):
    mask=(1<<bits)-1
    values=[0,*pis]
    for a,b in net.gates:
        values.append(signal(values,a,mask)&signal(values,b,mask))
    return values


def run(source,abc,work,previous):
    started=time.perf_counter()
    old=json.loads(previous.read_text())
    assert digest(source)==old["input_sha256"]
    net=Aig.read(source)
    choices,claimed,_=select(net)
    h=hashlib.sha256()
    for root,(leaves,cone,answer,_) in sorted(choices.items()):
        h.update(f'{root}/{leaves}/{sorted(cone)}/{answer["truth"]}\n'.encode())
    assert h.hexdigest()==old["cut_sha256"] and len(choices)==old["cuts"]
    original={g:original_endpoint(net,leaves,cone,g) for g,(leaves,cone,_,_) in choices.items()}
    pilot=patterns(source.stem,net.inputs,"calibration",4,512)
    training=packed_network(net,pilot,4096)
    fit=time.perf_counter()
    tree,tree_count,saved1=choose(net,choices,claimed,original,training,"tree")
    combined,extra_count,saved2=choose(net,choices,claimed,tree,training,"sharing")
    fit_time=time.perf_counter()-fit
    amended={g:(leaves,cone,dict(endpoints=(tree[g],combined[g])),cost)
             for g,(leaves,cone,_,cost) in choices.items()}
    nets=(net,replace(net,amended,claimed,0),replace(net,amended,claimed,1))
    areas=[len(x.gates) for x in nets]
    depths=[x.depth() for x in nets]
    assert areas[0]==areas[1] and areas[2]-areas[1]==extra_count and depths[2]<=depths[1]<=depths[0]
    mask=(1<<4096)-1
    train_totals=[sample(x,pilot,mask)[0] for x in nets]
    assert train_totals[0]-train_totals[1]==sum(saved1)
    assert train_totals[1]-train_totals[2]==sum(saved2)
    del training
    eq=[]
    for label,x in zip(("control","sharing"),nets[1:]):
        if not choices:
            assert x.gates==net.gates and x.outputs==net.outputs
            eq.append({"identity":True})
        else:
            variant=work/f"{source.stem}-{label}.aig"
            x.write(variant)
            eq.append(dict(**check_equivalent(abc,source,variant),sha256=digest(variant)))
    panels=[]
    for j in range(8):
        test=patterns(source.stem,net.inputs,f"validation-{j}",1,1024)
        obs=[sample(x,test,(1<<2048)-1) for x in nets]
        assert obs[0][1]==obs[1][1]==obs[2][1]
        panels.append([x[0] for x in obs])
    return dict(source_sha256=old["input_sha256"],cut_sha256=h.hexdigest(),cuts=len(choices),
                size_changes=tree_count,sharing_changes=extra_count,cpu=24,areas=areas,depths=depths,
                training_savings=[saved1,saved2],training_counts=train_totals,
                panels=panels,pairs_per_panel=1024,equivalence=eq,
                fit_s=fit_time,total_s=time.perf_counter()-started)


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    for arg in ("inputs","abc","work","original_results","out"):
        cli.add_argument(arg,type=Path)
    args=cli.parse_args()
    pin(24)
    args.work.mkdir(parents=True,exist_ok=True)
    args.out.mkdir(parents=True,exist_ok=True)
    for group,names in DESIGNS.items():
        for name in names.split():
            record=args.out/f"{name}.json"
            if record.exists():
                saved=json.loads(record.read_text())
                assert saved["source_sha256"]==digest(args.inputs/group/f"{name}.aig")
                continue
            data=run(args.inputs/group/f"{name}.aig",args.abc,args.work,args.original_results/f"{name}.json")
            record.write_text(json.dumps(data,indent=2)+"\n")
            print(name,data["size_changes"],data["sharing_changes"],data["depths"],round(data["total_s"],2),flush=True)
