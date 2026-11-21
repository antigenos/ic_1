"""Build a feasible four-input circuit by lifting a known subfunction through one output gate."""
import argparse
import itertools
import json
from pathlib import Path
from library import replay

PIS=[0xaaaa,0xcccc,0xf0f0,0xff00]


def normal(t):
    return t ^ (65535 if t&1 else 0)


def values(a,b):
    return {2:b&~a,4:a&~b,6:a^b,8:a&b,14:a|b}


def transform(t,mapping):
    return normal(sum(((t>>src)&1)<<dst for dst,src in enumerate(mapping)))


def upper(data,truth):
    target=normal(int(truth,16))
    maps=[[sum(((r>>p)&1)<<i for i,p in enumerate(perm)) ^ phase for r in range(16)]
          for perm in itertools.permutations(range(4)) for phase in range(16)]
    table={}
    for row in data["circuits"]:
        if row["activity"]<0: continue
        t=normal(int(row["truth"],16))
        for m in maps:
            table.setdefault(transform(t,m),(row,m))
    feasible=[(row["activity"]+2*g.bit_count()*(16-g.bit_count()),g,i,code)
              for g,(row,_) in table.items() for i,h in enumerate(PIS)
              for code,out in values(g,h).items() if out==target]
    score,g,pi,final=min(feasible)
    row,m=table[g]
    initial=PIS.copy()
    current=PIS.copy()
    labels=[PIS.index(transform(v,m)) for v in PIS]
    gates=[]
    for a,b,code in row["gates"]:
        w=values(initial[a],initial[b])[code]
        initial.append(w)
        h,l=sorted((labels[a],labels[b]),reverse=True)
        mapped=transform(w,m)
        op=next(k for k,v in values(current[h],current[l]).items() if v==mapped)
        gates.append([h,l,op])
        labels.append(len(current))
        current.append(mapped)
    assert current[-1]==g
    gates.append([len(current)-1,pi,final])
    witness=dict(truth=truth,activity=score,gates=gates,complement=int(truth,16)&1,direct=-2)
    replay(witness)
    return dict(status="feasible_upper_bound",source=row["truth"],source_optimum=row["activity"],
                transformed_partner=f"{g:04x}",primary=pi,witness=witness)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("library",type=Path)
    p.add_argument("truth")
    p.add_argument("output",type=Path)
    a=p.parse_args()
    result=upper(json.loads(a.library.read_text()),a.truth)
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(result["truth"] if "truth" in result else result["witness"]["truth"],result["witness"]["activity"])
