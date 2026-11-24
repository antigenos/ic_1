"""Apply both proved Pareto endpoints to the registered EPFL AIG corpus."""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import time
from audit import literals_cached
from run import digest, pin
from synthesize import solution
from verify_pareto import replay

VERSION="82d8cc6910419298e713a46644ed59fd3df53038"
DESIGNS={"arithmetic":"adder bar div hyp log2 max multiplier sin sqrt square",
         "random_control":"arbiter cavlc ctrl dec i2c int2float mem_ctrl priority router voter"}


class Aig:
    def __init__(self,inputs,outputs,gates):
        self.inputs=inputs
        self.outputs=outputs
        self.gates=gates

    @classmethod
    def read(cls,path):
        with path.open("rb") as src:
            magic,*fields=src.readline().split()
            m,i,l,o,a=map(int,fields[:5])
            assert magic==b"aig" and l==0 and m==i+a and all(int(v)==0 for v in fields[5:])
            outputs=[int(src.readline()) for _ in range(o)]
            payload=iter(src.read())
        def number():
            shift=value=0
            while True:
                byte=next(payload)
                value|=(byte&127)<<shift
                if byte<128:
                    return value
                shift+=7
        gates=[]
        for index in range(i+1,m+1):
            high=2*index-number()
            low=high-number()
            assert 0<=low<=high<2*index
            gates.append((low,high))
        assert all(x//2<=m for x in outputs)
        return cls(i,outputs,gates)

    def write(self,path):
        count=len(self.gates)
        data=bytearray(f"aig {self.inputs+count} {self.inputs} 0 {len(self.outputs)} {count}\n".encode())
        for out in self.outputs:
            data.extend(f"{out}\n".encode())
        def number(v):
            while v>=128:
                data.append(128|(v&127))
                v>>=7
            data.append(v)
        for index,(a,b) in enumerate(self.gates,self.inputs+1):
            low,high=sorted((a,b))
            assert 0<=low<=high<2*index
            number(2*index-high)
            number(high-low)
        path.write_bytes(data)

    def depth(self):
        levels=[0]*(self.inputs+1)
        for a,b in self.gates:
            levels.append(1+max(levels[a//2],levels[b//2]))
        return max(levels[out//2] for out in self.outputs)


def signal(values,lit,mask):
    return values[lit>>1] ^ (mask if lit&1 else 0)


cached_solution=lru_cache(8192)(solution)


def select(net):
    first=net.inputs+1
    refs=Counter(lit//2 for pair in net.gates for lit in pair)
    refs.update(lit//2 for lit in net.outputs)
    claimed=set()
    choices={}
    counts=Counter()
    for root in reversed(range(first,first+len(net.gates))):
        if root in claimed:
            continue
        leaves={root}
        cone=set()
        best=None
        best_key=None
        while len(leaves)<8:
            available=[v for v in leaves if v>=first and v not in claimed and (v==root or refs[v]==1)]
            if not available:
                break
            v=max(available)
            a,b=net.gates[v-first]
            leaves.remove(v)
            if a//2==b//2 or a//2 in leaves or b//2 in leaves or min(a,b)<2:
                break
            leaves.update((a//2,b//2))
            cone.add(v)
            n=len(leaves)
            if n<4:
                continue
            counts["examined"]+=1
            ordered=tuple(sorted(leaves))
            mask=(1<<(1<<n))-1
            values=dict(zip(ordered,literals_cached(n)))
            original_cost=0
            for g in sorted(cone):
                x,y=net.gates[g-first]
                t=signal(values,x,mask)&signal(values,y,mask)
                values[g]=t
                if g!=root:
                    p=t.bit_count()
                    original_cost+=2*p*((1<<n)-p)
            answer=cached_solution(n,values[root])
            if answer is None or len(answer["endpoints"])!=2:
                continue
            small,power=answer["endpoints"]
            counts["eligible"]+=1
            assert len(cone)==n-1 and original_cost>=small["activity"]>power["activity"]
            # Compare fractions by integer cross-multiplication, then width.
            gain=small["activity"]-power["activity"]
            key=(gain,small["activity"],n)
            if best_key:
                delta=gain*best_key[1]-best_key[0]*small["activity"]
                if delta<0 or (delta==0 and n<=best_key[2]):
                    continue
            best_key=key
            best=(ordered,frozenset(cone),answer,original_cost)
        if best:
            leaves,cone,answer,_=best
            for ep in answer["endpoints"]:
                replay(len(leaves),int(answer["truth"],16),ep)
            assert not (cone&claimed)
            claimed.update(cone)
            choices[root]=best
    return choices,claimed,counts


def replace(net,choices,claimed,endpoint):
    mapping=[2*i for i in range(net.inputs+1)]
    gates=[]
    def translated(lit):
        v=mapping[lit//2]
        assert v is not None
        return v^(lit&1)
    def add(a,b):
        gates.append((a,b))
        return 2*(net.inputs+len(gates))
    for index,(a,b) in enumerate(net.gates,net.inputs+1):
        if index in choices:
            leaves,_,answer,_=choices[index]
            ep=answer["endpoints"][endpoint]
            local=[translated(2*i) for i in leaves]
            for left,right,op in ep["gates"]:
                x,y=local[left],local[right]
                if op==14:
                    v=add(x^1,y^1)^1
                else:
                    assert op in (2,4,8)
                    v=add(x^(op==4),y^(op==2))
                local.append(v)
            mapping.append(local[-1]^ep["complement"])
        elif index in claimed:
            mapping.append(None)
        else:
            mapping.append(add(translated(a),translated(b)))
    return Aig(net.inputs,[translated(out) for out in net.outputs],gates)


def sample(net,pis,mask):
    values=[0,*pis]
    half=mask.bit_length()//2
    pairs_mask=(1<<half)-1
    counts=0
    for a,b in net.gates:
        v=signal(values,a,mask)&signal(values,b,mask)
        counts+=((v^(v>>half))&pairs_mask).bit_count()
        values.append(v)
    return counts,[signal(values,out,mask) for out in net.outputs]


def check_equivalent(abc,source,variant):
    original=Path(os.path.relpath(source,variant.parent)).as_posix()
    cmd=f'cec -n -T 60 "{original}" "{variant.name}"'
    start=time.perf_counter()
    run=subprocess.run([str(abc.resolve()),"-c",cmd],cwd=variant.parent,
                       capture_output=True,text=True,timeout=90,check=True)
    if not re.search(r"Networks are equivalent",run.stdout,re.I):
        raise RuntimeError(run.stdout[-1800:]+run.stderr[-500:])
    return dict(wall_s=time.perf_counter()-start,output=run.stdout.strip())


def case(source,git_blob,abc,work):
    start=time.perf_counter()
    raw=source.read_bytes()
    assert hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==git_blob
    net=Aig.read(source)
    choices,claimed,counts=select(net)
    small=replace(net,choices,claimed,0)
    power=replace(net,choices,claimed,1)
    nets=(net,small,power)
    areas=[len(network.gates) for network in nets]
    assert areas[0]==areas[1] and areas[2]-areas[1]==len(choices)
    eq={}
    for name,network in (("size",small),("activity",power)):
        if not choices:
            assert network.outputs==net.outputs and network.gates==net.gates
            eq[name]={"identity":True}
            continue
        variant=work/f"{source.stem}-{name}.aig"
        network.write(variant)
        disk=Aig.read(variant)
        assert disk.outputs==network.outputs and disk.gates==[tuple(sorted(pair)) for pair in network.gates]
        eq[name]=check_equivalent(abc,source,variant)
        eq[name]["sha256"]=digest(variant)
    panels=[]
    mask=(1<<1024)-1
    for panel in range(8):
        rng=random.Random(f"EPFL-20261124/{source.stem}/{panel}")
        pis=[rng.getrandbits(1024) for _ in range(net.inputs)]
        obs=[sample(network,pis,mask) for network in nets]
        assert obs[0][1]==obs[1][1]==obs[2][1]
        panels.append([pair[0] for pair in obs])
    strata=Counter()
    rates=[0.,0.,0.]
    cut_digest=hashlib.sha256()
    for root,(leaves,cone,answer,original) in sorted(choices.items()):
        n=len(leaves)
        strata[str(n)]+=1
        eps=answer["endpoints"]
        for i,cost in enumerate((original,eps[0]["activity"],eps[1]["activity"])):
            rates[i]+=cost/(1<<(2*n))
        cut_digest.update(f'{root}/{leaves}/{sorted(cone)}/{answer["truth"]}\n'.encode())
    return dict(version=VERSION,input_sha256=digest(source),git_blob=git_blob,
                cpu=24,abc_sha256=digest(abc),cuts=len(choices),cut_sha256=cut_digest.hexdigest(),
                examined=counts["examined"],eligible=counts["eligible"],widths=dict(strata),
                area=areas,depth=[v.depth() for v in nets],equivalence=eq,
                local_uniform_sum=rates,panels=panels,pairs_per_panel=512,wall_s=time.perf_counter()-start)


def main():
    parser=argparse.ArgumentParser()
    for arg in ("inputs","git_source","abc","work","out"):
        parser.add_argument(arg,type=Path)
    parser.add_argument("--only",choices=[s for names in DESIGNS.values() for s in names.split()])
    args=parser.parse_args()
    pin(24)
    args.work.mkdir(parents=True,exist_ok=True)
    args.out.mkdir(parents=True,exist_ok=True)
    listing=subprocess.check_output(["git","-C",str(args.git_source),"ls-tree","-r",VERSION],text=True)
    hashes={path:mode.split()[2] for line in listing.splitlines() for mode,path in [line.split("\t",1)]}
    for group,names in DESIGNS.items():
        for name in names.split():
            if args.only and name!=args.only:
                continue
            rel=f"{group}/{name}.aig"
            target=args.out/f"{name}.json"
            if target.exists():
                prior=json.loads(target.read_text())
                assert prior["git_blob"]==hashes[rel] and prior["version"]==VERSION
                continue
            record=case(args.inputs/rel,hashes[rel],args.abc,args.work)
            target.write_text(json.dumps(record,indent=2)+"\n")
            print(name,record["cuts"],record["area"],record["depth"],round(record["wall_s"],2),flush=True)


if __name__=="__main__":
    main()
