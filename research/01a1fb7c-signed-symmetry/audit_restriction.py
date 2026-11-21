"""Match every C lower bound and test SAT literal polarity at inclusive budgets."""
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from check_symmetry import FIRST,HERE,OPS,PINS,gate
from restriction import PARTS,bound,residual


def lower(t,k):
    return 2*max(sum(residual(t,0,r,k) for r in pair) for pair in PARTS)


def audit():
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        targets=[int(t,16) for t in json.loads(z.read("evidence/npn-family.json"))["essential"]]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        subprocess.run([sys.executable,str(HERE/"restriction.py"),"--header",str(root/"restriction_table.h")],check=True)
        exe=root/("probe.exe" if os.name=="nt" else "probe")
        subprocess.run(["gcc","-O2","-std=c11","-I",str(root),str(HERE/"restriction_probe.c"),"-o",str(exe)],check=True)
        def trace(requests,mode):
            return subprocess.check_output([str(exe)],text=True,env={**os.environ,"REPLAY_RESTRICTION":mode},
                input="".join(f"{t:04x} {n} {b}\n" for t,n,b in requests)).splitlines()
        lines=iter(trace([(t,2,-1) for t in targets],"size"))
        for t in targets:
            assert next(lines).split()==["T",f"{t:04x}",*(str(lower(t,k)) for k in range(5))]
            seen=set()
            for _ in range(30):
                label,hi,lo,op,*values=next(lines).split()
                g=gate(int(op),PINS[int(lo)],PINS[int(hi)])
                assert label=="G" and list(map(int,values))==[bound(t,g,k) for k in range(5)]
                seen.add(g)
            assert seen==FIRST
        assert next(lines,None) is None
        totals={}
        for mode in ("global","cost","size"):
            requests=[]
            known=[]
            for t in (0x0189,0x03dd):
                for n in range(2,9):
                    k=4 if mode=="cost" else min(n-2,4)
                    glob=lower(t,min(4,k+1))
                    options={}
                    for hi in range(1,4):
                        for lo in range(hi):
                            for op in OPS:
                                v=1+3*n
                                clause=(2*(v+hi)+1,2*(v+4+lo)+1,*(2*j+((op>>j)&1) for j in range(1,4)))
                                options[clause]=bound(t,gate(op,PINS[lo],PINS[hi]),k)
                    thresholds={glob,*options.values()}
                    for b in sorted(thresholds|{x-1 for x in thresholds if x}):
                        passed=glob<=b and (mode=="global" or any(q<=b for q in options.values()))
                        cut=Counter(c for c,q in options.items() if q>b and passed and mode!="global")
                        requests.append((t,n,b))
                        known.append((passed,cut))
            output=iter(trace(requests,mode))
            for (t,n,b),(ok,expected) in zip(requests,known):
                assert next(output)==f"Q {t:04x} {n} {b}"
                assert next(output)==f"P {int(ok)}"
                actual=Counter()
                for _ in range(expected.total()):
                    label,*rest=next(output).split()
                    assert label=="C"
                    actual[tuple(map(int,rest))]+=1
                assert actual==expected
            assert next(output,None) is None
            totals[mode]=dict(windows=len(requests),clauses=sum(c.total() for _,c in known))
    return dict(functions=len(targets),conditional_bounds=len(targets)*30*5,
                unconditional_bounds=len(targets)*5,threshold_tests=totals)


if __name__=="__main__":
    print(json.dumps(audit(),indent=2))
