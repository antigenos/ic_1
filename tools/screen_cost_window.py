"""Recompute old and proposed joint supports from real saturation-point snapshots."""
from collections import Counter
from itertools import chain
import argparse
import json
from pathlib import Path
from audit_trail import OPS, possible


def activity(a):
    return 2*a*(16-a)


def values(mask):
    return [a for a in range(1,9) if mask & (1<<a)]


def measure(path):
    totals, examples, unique = Counter(), {}, set()
    for line in path.read_text().splitlines():
        if not line.startswith("WINDOW "):
            continue
        fields=line.split()
        target,gates,lo,hi,j,k,opened,ops,sx,sy=map(int,fields[1:11])
        signals=[tuple(map(int,raw.split(","))) for raw in fields[11:]]
        assert len(signals)==4+gates-1
        zx,ox,dx,ux=signals[j]
        zy,oy,dy,uy=signals[k]
        costs=[[activity(a) for a in values(signals[g][2])] for g in range(4,len(signals)) if g not in (j,k)]
        # Exact attainable sums, independently cross-checked with a packed bitset.
        sums={0}
        bits=1
        for group in costs:
            sums={v+c for v in sums for c in group}
            newbits=0
            for c in group:
                newbits |= bits<<c
            bits=newbits
        assert bits==sum(1<<v for v in sums)
        least,most=min(sums),max(sums)
        masks=[[0,0] for _ in range(3)]
        reach=set(chain.from_iterable(possible(16,target,op,zx,ox,zy,oy)
                        for t,op in enumerate(OPS) if ops>>t&1))
        for a,b in reach:
            if not (dx>>a&1 and dy>>b&1):
                continue
            used=(activity(a) if j>=4 else 0)+(activity(b) if k>=4 else 0)
            tests=(used+least<=hi, used+least<=hi and used+most>=lo,
                   any(lo<=used+v<=hi for v in sums))
            for m,t in zip(masks,tests):
                if t:
                    m[0]|=1<<a
                    m[1]|=1<<b
        assert masks[0]==[sx,sy], (line,masks)
        totals["observations"]+=1
        unique.add(tuple(fields[1:]))
        for old,new,label in ((0,1,"two_sides"),(1,2,"holes"),(0,2,"total")):
            if opened==-1:
                extra=((masks[old][0]&~masks[new][0]&ux).bit_count()+
                       (masks[old][1]&~masks[new][1]&uy).bit_count())
            else:
                extra=int(bool(masks[old][0]) and not masks[new][0])
            totals[label+"_new_pending_literals"]+=extra
            if extra:
                totals[label+"_observations"]+=1
                examples.setdefault(label,dict(snapshot=line,old=masks[old],new=masks[new],
                                    remaining_sums=sorted(sums),extra=extra))
    assert totals["observations"]
    return dict(counts=totals,distinct_snapshots=len(unique),examples=examples)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("log",type=Path)
    print(json.dumps(measure(p.parse_args().log),indent=2))
