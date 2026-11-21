"""Decode clauses produced by the actual SAT integration, then find an independent row bijection."""
from functools import cache
import json
from check_orbits import HERE, OPS, image, normal, op, pins
from probe_prefix import boundary_group


@cache
def selectors(n):
    start=1+3*n
    v={}
    for g in range(4,4+n):
        for p in (0,1):
            for j in range(g-p):
                v[start]=g,p,j
                start+=1
    return v


@cache
def proof(n,lits,target):
    vals=pins(4)
    inputs=[]
    for g in (4,5,6):
        hi,lo,*control=lits[5*(g-4):5*(g-3)]
        assert hi&1 and lo&1
        gh,ph,h=selectors(n)[hi>>1]
        gl,pl,l=selectors(n)[lo>>1]
        assert (gh,ph,gl,pl)==(g,0,g,1) and h>l
        assert [x>>1 for x in control]==[3*(g-4)+i for i in (1,2,3)]
        code=sum((x&1)<<i for i,x in enumerate(control,1))
        assert code in OPS
        vals.append(op(code,vals[l],vals[h]))
        inputs.append((l,h))
    unmet=frozenset(range(6))-set(inputs[0]+inputs[1])
    return verify(tuple(vals[:6]),vals[6],unmet,target)


@cache
def verify(columns,third,unmet,target):
    return any(normal(image(third,row),65535)<third for row,m in maps(columns,unmet,target))


@cache
def maps(columns,unmet,target):
    return tuple(boundary_group(target,columns,unmet))


if __name__=="__main__":
    log=HERE/"evidence/trace-conditional-0189/solver.log"
    total=0
    for line in log.read_text().splitlines():
        if line.startswith("PREFIX "):
            header,n,*ss=line.split()
            lits=tuple(map(int,ss))
            assert len(lits)==15 and proof(int(n.split("=")[1]),lits,0xfe76)
            total+=1
    assert total
    print(json.dumps(dict(actual_clauses=total,distinct_by_size_and_literals=proof.cache_info().currsize,
                          all_have_strict_row_transform=True),indent=2))
