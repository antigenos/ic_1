"""Exhaust all 900 primary-only prefixes against actual compressed native clauses."""
from collections import Counter
from itertools import combinations, product
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from audit_family import expected
from check_pair import images, least
from check_order import KEYS
from check_symmetry import HERE, OPS, PINS, gate

DESCS = [(i,j,op,gate(op,PINS[i],PINS[j])) for i,j in combinations(range(4),2) for op in OPS]
PREFIXES = list(product(DESCS,repeat=2))


def falsification_masks(n):
    where,selector={},{}
    var=1+3*n
    for obj in (4,5):
        for pin in range(2):
            for operand in range(obj-pin):
                where[obj,pin,operand]=var
                selector[var]=(obj,pin,operand)
                var+=1
    masks={}
    for idx,prefix in enumerate(PREFIXES):
        for k,(lo,hi,op,h) in enumerate(prefix):
            slot=4+k
            # Only negative literal on a selected pin can be falsified.
            for v in (where[slot,0,hi],where[slot,1,lo]):
                lit=2*v+1
                masks[lit]=masks.get(lit,0)|(1<<idx)
            for bit in range(3):
                lit=2*(1+3*k+bit)+(op>>(1+bit)&1)
                masks[lit]=masks.get(lit,0)|(1<<idx)
    return selector,masks


def main():
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        targets=[int(t,16) for t in json.loads(z.read("evidence/npn-family.json"))["essential"]]
    cases=[(t,n) for t in targets for n in (2,3,7)]
    assignments={n:falsification_masks(n) for n in (2,3,7)}
    summary={}
    with TemporaryDirectory() as tmp:
        exe=Path(tmp)/("emit.exe" if os.name=="nt" else "emit")
        subprocess.run(["gcc","-std=c11","-O2",str(HERE/"emit_clauses.c"),"-o",str(exe)],check=True)
        for mode in ("sorted-prefix","orbit-prefix"):
            env={k:v for k,v in os.environ.items() if not k.startswith("REPLAY_FIRST")}
            env["REPLAY_FIRST_SYMMETRY"]=mode
            raw=subprocess.check_output([str(exe)],env=env,text=True,input="".join(f"{t:x} {n}\n" for t,n in cases))
            blocks=raw.lstrip("Q ").split("\nQ ")
            assert len(blocks)==len(cases)
            total=checked=0
            for (t,n),block in zip(cases,blocks):
                head,*rows=block.splitlines()
                assert head==f"{t:04x} {n}"
                native=Counter(tuple(sorted(map(int,s.split()[1:]))) for s in rows)
                base=expected(t,n,"combined")
                assert not base-native
                extra=native-base
                if n==2:
                    assert not extra
                    continue
                selector,masks=assignments[n]
                blocked=0
                for clause in extra:
                    sel=[selector[v>>1] for v in clause if v>>1 in selector]
                    assert len(sel)==4 and {(x,y) for x,y,z in sel}=={(4,0),(4,1),(5,0),(5,1)}
                    assert all(z<4 for x,y,z in sel)
                    cover=(1<<900)-1
                    for lit in clause:
                        cover &= masks[lit]
                    blocked |= cover
                total += extra.total()
                for idx,(a,b) in enumerate(PREFIXES):
                    x,y=a[-1],b[-1]
                    if KEYS[x]!=least(t,x):
                        continue
                    valid=KEYS[x]<=KEYS[y]
                    if valid and mode=="orbit-prefix":
                        best=min(tuple(sorted((KEYS[u],KEYS[v]))) for u,v in zip(images(t,x),images(t,y)))
                        valid=(KEYS[x],KEYS[y])==best
                    assert bool(blocked>>idx & 1)!=valid,(t,n,mode,a,b)
                    checked+=1
            summary[mode]=dict(compressed_clauses=total,reachable_valuations_checked=checked)
    return dict(functions=len(targets),gate_counts=[2,3,7],modes=summary)


if __name__=="__main__":
    print(json.dumps(main(),indent=2))
