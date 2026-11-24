"""Check every four-input signed action and partner minimum with independent finite constructions."""
import argparse
from array import array
from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path
import sys

INF=1000000


def group_and_orbits(representatives, maps):
    raw=maps.read_bytes()
    assert len(raw)==384*65536
    native={sha256(raw[j:j+65536]).digest() for j in range(0,len(raw),65536)}
    assert len(native)==384
    classes=[-1]*65536
    for order in permutations(range(4)):
        for phase in range(16):
            dest=[sum(((i>>bit)&1)<<position for bit,position in enumerate(order))^phase
                  for i in range(16)]
            lo=[0]*256
            hi=[0]*256
            for b in range(1,256):
                j=(b&-b).bit_length()-1
                lo[b]=lo[b&(b-1)] | (1<<dest[j])
                hi[b]=hi[b&(b-1)] | (1<<dest[8+j])
            transformed=array('H')
            for h in hi:
                transformed.extend((z^65535 if z&1 else z) for z in (h|l for l in lo[::2]))
            if sys.byteorder!='little': transformed.byteswap()
            native.remove(sha256(transformed.tobytes()).digest())
            for f in representatives:
                v=lo[f&255]|hi[f>>8]
                t=v^65535 if v&1 else v
                assert classes[t] in (-1,f)
                classes[t]=f
    assert not native and all(f>=0 for f in classes[::2])
    return classes


def validate(maps, matrix, tables):
    registered={}
    for line in matrix.read_text().splitlines():
        p,f,m=map(int,line.split())
        assert (p,f) not in registered
        registered[p,f]=m
    reps=sorted({f for p,f in registered})
    assert len(reps)==222 and len(registered)==221*222
    classes=group_and_orbits(reps,maps)
    qs=sorted(range(2,65536,2),key=lambda t: 2*t.bit_count()*(16-t.bit_count()))
    w={q:2*q.bit_count()*(16-q.bit_count()) for q in qs}
    double={f:INF for f in reps}
    for p in reps[1:]:
        observed={}
        for q in qs:
            for t in (q & p,q | p,q ^ p,p & ~q,q & ~p):
                f=classes[t]
                if f not in observed: observed[f]=w[q]
        for f in reps:
            m=observed.get(f,INF)
            assert m==registered[p,f],(p,f,m,registered[p,f])
            double[f]=min(double[f],m+w[p])
    for f in reps:
        a=min(f.bit_count(),16-f.bit_count())
        x=max(1,a-1)
        assert double[f]>=30+2*x*(16-x)
    outcomes=[]
    for path in tables:
        rows=[line.split() for line in path.read_text().splitlines()]
        meta=next(r for r in rows if r[0]=='meta')
        b0=int(meta[-1])
        profile={}
        for row in rows:
            if row[0]=='profile': profile[int(row[1])]=int(row[2])
        checked=0
        for row in rows:
            if row[0]!='target': continue
            f,u,lower,uniform=map(int,row[1:5])
            a=min(f.bit_count(),16-f.bit_count())
            x=max(1,a-1)
            unseen=min(b0+30+2*x*(16-x),*(b+registered[p,f] for p,b in profile.items()))
            assert min(u,unseen)==lower and min(u,b0+30)==uniform
            checked+=1
        assert checked==222
        outcomes.append(dict(cap=int(meta[2]),verified=checked,sha256=sha256(path.read_bytes()).hexdigest()))
    return dict(group_actions=384,normalized_truths_per_action=32768,
                checked_images=384*32768,partner_cells=len(registered),
                tested_operand_pairs=221*32767,classes=222,bounds=outcomes)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('maps',type=Path)
    p.add_argument('matrix',type=Path)
    p.add_argument('report',type=Path)
    p.add_argument('tables',type=Path,nargs='+')
    args=p.parse_args()
    result=validate(args.maps,args.matrix,args.tables)
    args.report.write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
