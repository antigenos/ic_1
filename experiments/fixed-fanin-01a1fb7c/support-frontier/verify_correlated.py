"""Enumerate unrestricted read-once factorizations and literal permutations."""
from functools import lru_cache
from itertools import permutations
import json
from pathlib import Path
import random
import sys
from correlated import Optimizer,path_lengths,transition_panels
from verify_pareto import expanded_indices
from workload import verify_truth


def independently_enumerate_tree(n,t,values,arrivals,pairs):
    all_bits=(1<<(2*pairs))-1
    def cost(v):
        return ((v^(v>>pairs))&((1<<pairs)-1)).bit_count()
    @lru_cache(None)
    def trees(ids,table):
        m=len(ids)
        if m==1:
            return ((0,arrivals[ids[0]]),)
        v=0
        for row in range(1<<m):
            if (table>>row)&1:
                match=all_bits
                for j,i in enumerate(ids):
                    match&=values[i] if (row>>j)&1 else values[i]^all_bits
                v|=match
        gate_cost=cost(v)
        answer=[]
        for mask in range(1,(1<<m)-1,2):
            a=tuple(i for i in range(m) if mask>>i&1)
            b=tuple(i for i in range(m) if not(mask>>i&1))
            matrix=[tuple((table>>(x|y))&1 for y in expanded_indices(b)) for x in expanded_indices(a)]
            cols=list(zip(*matrix))
            if len(set(matrix))!=2 or len(set(cols))!=2:
                continue
            ua=sum((row!=matrix[0])<<j for j,row in enumerate(matrix))
            vb=sum((col!=cols[0])<<j for j,col in enumerate(cols))
            for c1,d1 in trees(tuple(ids[i] for i in a),ua):
                for c2,d2 in trees(tuple(ids[i] for i in b),vb):
                    answer.append((c1+c2+gate_cost,max(d1,d2)+1))
        return tuple(answer)
    return trees(tuple(range(n)),t)


def exhaustive_chains(a,b,point,values,arrivals,pairs):
    mask=(1<<(2*pairs))-1
    options=[]
    for first in permutations(a):
        for second in permutations(b):
            v=mask
            cost=0
            for j,i in enumerate((*first,*second)):
                v &= values[i] if (point>>i)&1 else values[i]^mask
                if j==0:
                    depth=arrivals[i]
                else:
                    depth=max(depth,arrivals[i])+1
                    cost+=((v^(v>>pairs))&((1<<pairs)-1)).bit_count()
                if j==len(a)-1:
                    enable=v
            out=enable&~v
            options.append((cost+((out^(out>>pairs))&((1<<pairs)-1)).bit_count(),depth+1))
    return options


def main():
    path=Path(sys.argv[1])
    if path.exists():
        raise FileExistsError(path)
    rng=random.Random(8277)
    checked=0
    for n,k in ((4,2),(5,2),(5,3),(6,3),(7,4)):
        for scenario in range(4):
            indices=list(range(n))
            rng.shuffle(indices)
            a,b=indices[k:],indices[:k]
            fixed=sum(1<<i for i in a)
            point=rng.randrange(1<<n)
            t=sum(1<<r for r in range(1<<n) if not((r^point)&fixed) and r!=point)
            if scenario&1:
                t^=(1<<(1<<n))-1
            values=[rng.getrandbits(128) for _ in range(n)]
            if scenario>=1:
                values[0]&=values[1]
            if scenario>=2:
                values[2]=values[0]
            if scenario==3:
                values[3]=0
            arrivals=[rng.randrange(5) for _ in range(n)]
            ref_tree=independently_enumerate_tree(n,t,values,arrivals,64)
            ref_share=exhaustive_chains(a,b,point,values,arrivals,64)
            for family,options in (("tree",ref_tree),("sharing",ref_share)):
                solver=Optimizer(t,values,64,arrivals)
                for deadline in range(1,max(arrivals)+n+2):
                    best=min((c for c,d in options if d<=deadline),default=None)
                    got=solver.endpoint(family,deadline)
                    assert best==(got[0] if got is not None else None),(n,k,scenario,family,deadline)
                    if got:
                        c,ep=got
                        assert sum(transition_panels(values,ep,16,4))==c
                        assert max(i+j for i,j in zip(arrivals,path_lengths(n,ep)))<=deadline
                        verify_truth(n,t,ep)
                    checked+=1
    path.write_text(json.dumps(dict(optimum_deadline_checks=checked,variable_counts=[4,5,6,7],
                                    scenarios_per_split=4,all_matched=True),indent=2)+"\n")
    print(checked,"exact empirical optima and timing boundaries agree.")


if __name__=="__main__":
    main()
