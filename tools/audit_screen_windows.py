"""Independently verify emitted native window clauses, with real lower and upper limits."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys
from audit_trail import variable_map, possible, OPS


def reason(line, lower, upper, discrete):
    tok=line.split()
    n,gates=map(int,tok[1:3])
    t=int(tok[3],16)
    cap,j,k,opened=map(int,tok[4:8])
    lits=list(map(int,tok[8:]))
    rows=1<<n
    assert cap==upper and lits[0]&1 and len({v>>1 for v in lits})==len(lits)
    vm=variable_map(n,gates)
    dom=[set(range(1,rows//2+1)) for _ in range(n+gates-1)]
    z=[1]*len(dom)
    o=[0]*len(dom)
    for i in range(n):
        o[i]=sum((r>>i&1)<<r for r in range(rows))
        z[i]=((1<<rows)-1)^o[i]
        dom[i]={rows//2}
    sel={}
    ops=set(OPS)
    for lit in lits[1:]:
        kind,*v=vm[lit>>1]
        val=lit&1
        if kind=="sel":
            assert val and v[0] not in sel
            sel[v[0]]=v[1]
        elif kind=="op":
            ops={op for op in ops if op>>(1+v[0])&1==val}
        elif kind=="row":
            assert v[0] in (j,k)
            (o if val else z)[v[0]]|=1<<v[1]
        else:
            assert kind=="count" and not val
            dom[v[0]].remove(v[1])
    victim=vm[lits[0]>>1]
    if opened==-1:
        assert victim[0]=="count" and victim[1] in (j,k)
        dom[victim[1]].intersection_update({victim[2]})
    else:
        assert opened not in sel and victim==("sel",opened,(j,k)[opened])
        sel[opened]=victim[2]
    assert sel=={0:j,1:k}
    weight=lambda a: 2*a*(rows-a)
    sums={0}
    for g in range(n,len(dom)):
        if g not in (j,k):
            sums={s+weight(a) for s in sums for a in dom[g]}
    for op in ops:
        for a,b in possible(rows,t,op,z[j],o[j],z[k],o[k]):
            if a not in dom[j] or b not in dom[k]:
                continue
            used=(weight(a) if j>=n else 0)+(weight(b) if k>=n else 0)
            feasible=(any(lower<=used+s<=upper for s in sums) if discrete else
                      used+min(sums)<=upper and used+max(sums)>=lower)
            assert not feasible,(line,lower,upper,op,a,b)
    return victim[0]


def run(path,discrete):
    counts,total=Counter(),Counter()
    raw=gzip.decompress(path.read_bytes()) if path.suffix==".gz" else path.read_bytes()
    for line in raw.decode().splitlines():
        if line.startswith("WINDOW_BOUND "):
            lower,upper=map(int,line.split()[1:])
        elif line.startswith("REASON "):
            counts[reason(line,lower,upper,discrete)]+=1
        elif line.startswith("JOINT "):
            vals=dict(v.split("=") for v in line.split()[1:])
            total["sel"]+=int(vals["edges"])
            total["count"]+=int(vals["counts"])
    assert counts==total and sum(counts.values())
    return dict(verified=counts,raw_sha256=hashlib.sha256(raw).hexdigest())


if __name__=="__main__":
    print(json.dumps({mode:run(Path(path),mode=="holes") for mode,path in
                      (arg.split("=",1) for arg in sys.argv[1:])},indent=2))
