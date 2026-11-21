"""Independently enumerate the five-gate 0189 query and audit each SAT assumption."""
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from repeat_0189 import pin


def functions(x,y):
    return (x & ~y, y & ~x, x ^ y, x & y, x | y)


def enumerate_gates():
    pins=[0xaaaa,0xcccc,0xf0f0,0xff00]
    valid=Counter()
    leaves=0
    codes=(2,4,6,8,14)
    def visit(signals,used,cost):
        nonlocal leaves
        if len(signals)==8:
            if cost!=304:
                return
            leaves+=1
            for j,y in enumerate(signals[:-1]):
                if (used | (1<<7) | (1<<j))!=255:
                    continue
                for code,t in zip(codes,functions(signals[-1],y)):
                    if t==0xfe76:
                        valid[code]+=1
            return
        for hi,x in enumerate(signals):
            for lo,y in enumerate(signals[:hi]):
                for g in functions(x,y):
                    a=g.bit_count()
                    if a==0 or a==16:
                        continue
                    nc=cost+2*a*(16-a)
                    if nc+(7-len(signals))*30<=304:
                        visit(signals+[g], used | (1<<hi) | (1<<lo), nc)
    visit(pins,0,0)
    return leaves,dict(valid)


def check(dest):
    pin(10)
    dest.mkdir(parents=True,exist_ok=False)
    leaves,counts=enumerate_gates()
    binary=ROOT/".local/variants/fixed-fanin-partition"/("abc.exe" if os.name=="nt" else "abc")
    env={k:v for k,v in os.environ.items() if not k.startswith(("FF_","REPLAY_"))}
    env["FF_PARTITION_AUDIT"]="1"
    log=subprocess.run([binary,"-c","pexact -I 4 -M 2 0189"],cwd=dest,env=env,capture_output=True,
                       check=True,timeout=60).stdout
    (dest/"solver.log").write_bytes(log)
    matches=re.findall(rb"FF_SPLIT gates=5 bound=304 code=(\d+) result=(-?\d+)",log)
    found={int(op):int(result) for op,result in matches}
    assert sorted(found)==[2,4,6,8,14] and b"FF_UNRESTRICTED result=1" in log
    assert all(v==(1 if counts.get(op) else -1) for op,v in found.items()), (found,counts)
    result=dict(complete_internal_sequences_at_304=leaves, feasible_circuits_by_code=counts,
                solver_by_code=found, unrestricted="SAT")
    (dest/"audit.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))


if __name__=="__main__":
    check(Path(sys.argv[1]).resolve())
