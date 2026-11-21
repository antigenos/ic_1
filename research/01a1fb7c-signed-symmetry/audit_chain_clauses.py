"""Check the compiled chain comparator, first choices and every secondary gate's cut."""
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from audit_family import expected
from audit_pair_clauses import PREFIXES
from check_chain import least_rank, rank
from check_symmetry import HERE, OPS, PINS, gate


def encoding(n):
    loc=1+3*n
    sel={}
    for i in range(4,4+n):
        for k in range(2):
            for j in range(i-k):
                sel[i,k,j]=loc
                loc+=1
    clauses=[]
    for i in range(4,3+n):
        for h in range(1,i):
            lower=[2*sel[i+1,0,u] for u in range(h,i+1)]
            clauses.append(tuple(sorted([2*sel[i,0,h]+1,*lower])))
            for l in range(1,h):
                tail=[2*sel[i+1,1,v] for v in range(l,h)]
                clauses.append(tuple(sorted([2*sel[i,0,h]+1,2*sel[i+1,0,h]+1,2*sel[i,1,l]+1,*tail])))
    return sel, Counter(clauses)


def masks(sel,other):
    result={}
    for i,desc in enumerate(PREFIXES):
        for obj,(lo,hi,op,_) in zip((4,other),desc):
            false=[2*sel[obj,0,hi]+1,2*sel[obj,1,lo]+1]
            false.extend(2*(1+3*(obj-4)+bit)+(op>>(1+bit)&1) for bit in range(3))
            for lit in false:
                result[lit]=result.get(lit,0) | (1<<i)
    return result


def audit():
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        targets=[int(v,16) for v in json.loads(z.read("evidence/npn-family.json"))["essential"]]
    n=7
    sel,base=encoding(n)
    decoded={v:k for k,v in sel.items()}
    masks_for={j:masks(sel,j) for j in range(5,3+n)}
    report={}
    with TemporaryDirectory() as tmp:
        exe=Path(tmp)/("emit.exe" if os.name=="nt" else "emit")
        subprocess.run(["gcc","-std=c11","-O2",str(HERE/"emit_clauses.c"),"-o",str(exe)],check=True)
        for mode in ("chain","chain-first","chain-orbit"):
            env={k:v for k,v in os.environ.items() if not k.startswith("REPLAY_FIRST")}
            env["REPLAY_FIRST_SYMMETRY"]=mode
            stream=subprocess.check_output([str(exe)],input="".join(f"{t:x} {n}\n" for t in targets),text=True,env=env)
            total=0
            blocks=stream.lstrip("Q ").split("\nQ ")
            assert len(blocks)==len(targets)
            for t,block in zip(targets,blocks):
                head,*rows=block.splitlines()
                assert head==f"{t:04x} {n}"
                native=Counter(tuple(sorted(map(int,s.split()[1:]))) for s in rows)
                required=base+expected(t,n,"first-use")
                if mode!="chain":
                    for hi in range(1,4):
                        for lo in range(hi):
                            for op in OPS:
                                h=gate(op,PINS[lo],PINS[hi])
                                if rank(h)!=least_rank(t,h):
                                    c=[2*sel[4,0,hi]+1,2*sel[4,1,lo]+1]
                                    c.extend(2*i+(op>>i&1) for i in range(1,4))
                                    required[tuple(sorted(c))]+=1
                assert not required-native
                extra=native-required
                if mode!="chain-orbit":
                    assert not extra
                else:
                    killed=dict.fromkeys(masks_for,0)
                    for c in extra:
                        pins=[decoded[v>>1] for v in c if v>>1 in decoded]
                        other=max(o for o,_,_ in pins)
                        assert other in masks_for and len(pins)==4 and all(p<4 for _,_,p in pins)
                        assert {(o,k) for o,k,_ in pins}=={(4,0),(4,1),(other,0),(other,1)}
                        cover=(1<<900)-1
                        for lit in c:
                            cover &= masks_for[other][lit]
                        killed[other]|=cover
                    for i,(a,b) in enumerate(PREFIXES):
                        first,second=a[-1],b[-1]
                        if rank(first)==least_rank(t,first):
                            assert all(bool(mask>>i & 1)==(rank(first)>least_rank(t,second)) for mask in killed.values())
                total+=native.total()
            report[mode]=total
    return dict(functions=len(targets),total_gates=n,secondary_gate_ids=list(masks_for),matched_clauses=report)


if __name__=="__main__":
    print(json.dumps(audit(),indent=2))
