"""Score all valid first-gate assignments against literals emitted by the native filtering body."""
from itertools import combinations
import json
import os
from pathlib import Path
import subprocess
from check_orbits import HERE, OPS, op, pins, representatives


def run():
    out=HERE.parents[1]/".local"/("orbit-clause-check.exe" if os.name=="nt" else "orbit-clause-check")
    out.parent.mkdir(exist_ok=True)
    root=HERE.parents[1]
    subprocess.run(["gcc","-std=c11","-O2",str((HERE/"check_native_orbits.c").relative_to(root)),
                    "-o",str(out.relative_to(root))],cwd=root,check=True)
    family=json.loads((HERE/"reproduction/evidence/npn-family.json").read_text())["essential"]
    cases=[(int(t,16)^phase,n) for t in family for phase in (0,65535) for n in (3,7,10)]
    request="".join(f"{t:04x} {n}\n" for t,n in cases)
    result={}
    for mode in ("off","perm","signed"):
        env={k:v for k,v in os.environ.items() if not k.startswith("PEXACT_ORBIT")}
        env["PEXACT_ORBIT"]=mode
        raw=subprocess.check_output([str(out)],input=request,env=env,text=True)
        blocks={}
        for line in raw.splitlines():
            if line.startswith("T "):
                _,label,n=line.split()
                key=int(label,16),int(n)
                blocks[key]=[]
            else:
                blocks[key].append(tuple(int(x) for x in line.split()))
        assert len(blocks)==len(cases)
        count=0
        num_clauses=0
        for t,n in cases:
            clauses=blocks[t,n]
            num_clauses+=len(clauses)
            keep=representatives(4,t,mode=="signed")
            for lo,hi in combinations(range(4),2):
                for op_code in OPS:
                    # First pin block covers inputs 0..3; second covers 0..2.
                    ones={1+3*n+hi,1+3*n+4+lo}
                    ones.update(v for v in (1,2,3) if (op_code>>v)&1)
                    sat=all(any(((lit>>1) in ones) != bool(lit&1) for lit in clause)
                            for clause in clauses)
                    truth=op(op_code,pins(4)[lo],pins(4)[hi])
                    assert sat==(mode=="off" or truth in keep),(t,n,hi,lo,op_code,clauses)
                    count+=1
        result[mode]=dict(checked_assignments=count,emitted_clauses=num_clauses)
    return dict(classes=len(family),target_phases=2,gate_counts=[3,7,10],modes=result)


if __name__=="__main__":
    print(json.dumps(run(),indent=2))
