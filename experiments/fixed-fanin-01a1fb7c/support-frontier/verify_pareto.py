"""Target-driven read-once optimizer and independent endpoint checks."""
import argparse
from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
import random
import time
from audit import full
from crosscheck import signed_images
from run import pin
from synthesize import abc, solution


@lru_cache(None)
def expanded_indices(variables):
    return tuple(sum(((assignment>>j)&1)<<i for j,i in enumerate(variables))
                 for assignment in range(1<<len(variables)))


@lru_cache(None)
def tree_inclusive(n,t):
    """Minimum activity of a read-once tree including its root, in local rows."""
    rows=1<<n
    if n==1:
        return 0 if t in (1,2) else None
    best=None
    # An ordered partition and its reverse permit the same binary functions.
    for split in range(1,rows-1,2):
        a=tuple(i for i in range(n) if (split>>i)&1)
        b=tuple(i for i in range(n) if not (split>>i)&1)
        aa,bb=expanded_indices(a),expanded_indices(b)
        groups=[]
        first_column_bit=0
        for i in aa:
            pattern=sum(((t>>(i|j))&1)<<index for index,j in enumerate(bb))
            if pattern not in groups:
                groups.append(pattern)
            if len(groups)>2:
                break
            if pattern!=groups[0]:
                first_column_bit|=1<<aa.index(i)
        if len(groups)!=2:
            continue
        patterns=[((groups[0]>>j)&1)+2*((groups[1]>>j)&1) for j in range(len(bb))]
        if len(set(patterns))!=2:
            continue
        second=sum((v!=patterns[0])<<j for j,v in enumerate(patterns))
        ca,cb=tree_inclusive(len(a),first_column_bit),tree_inclusive(len(b),second)
        if ca is None or cb is None:
            continue
        value=(ca<<(2*len(b)))+(cb<<(2*len(a)))+2*t.bit_count()*(rows-t.bit_count())
        best=value if best is None else min(value,best)
    return best


def independent_tree_cost(n,t):
    value=tree_inclusive(n,t)
    return None if value is None else value-2*t.bit_count()*((1<<n)-t.bit_count())


def replay(n,t,ep):
    rows=1<<n
    gates=ep["gates"]
    ones=[0]*len(gates)
    generated=0
    used=set()
    for row in range(rows):
        wires=[(row>>i)&1 for i in range(n)]
        for g,(a,b,op) in enumerate(gates):
            assert a!=b and 0<=a<len(wires) and 0<=b<len(wires)
            assert op in (2,4,6,8,14)
            v=(op>>(wires[a]+2*wires[b]))&1
            wires.append(v)
            ones[g]+=v
            if row==0:
                used.update((a,b))
        generated|=(wires[-1]^ep["complement"])<<row
    assert generated==t and len(gates)==ep["gate_count"]
    assert used==set(range(n+len(gates)-1))
    assert ep["activity"]==sum(2*x*(rows-x) for x in ones[:-1])


def measure(n,t,expected=None):
    answer=solution(n,t)
    assert answer and full(t,n)
    endpoints=answer["endpoints"]
    for e in endpoints:
        replay(n,t,e)
    first,last=endpoints[0],endpoints[-1]
    assert first["gate_count"]==n-1
    assert first["activity"]==independent_tree_cost(n,t)
    if len(endpoints)==2:
        assert last["gate_count"]==n and last["activity"]<first["activity"]
    if expected is not None:
        assert last["activity"]==expected
    return first["activity"],last["activity"]


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("output",type=Path)
    cli.add_argument("--abc",type=Path,required=True)
    args=cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    pin(24)
    start=time.perf_counter()
    here=Path(__file__).resolve().parent
    low={}
    records=json.loads((here.parent/"evidence/leaves-690.json").read_text())["circuits"]
    for w in records:
        if w["activity"]<=182:
            for folded in set(signed_images(4,int(w["truth"],16))):
                low[folded]=low[65535^folded]=w["activity"]
    counts=Counter()
    for truth in range(65536):
        result=solution(4,truth)
        assert bool(result)==(truth in low), truth
        if result:
            measure(4,truth,low[truth])
            counts[result["family"]]+=1
    rng=random.Random(20261123)
    split_rows=[]
    transformed=0
    for n in range(4,9):
        for k in range(2,n):
            q=n-k
            prices=None
            for iteration in range(4):
                order=list(range(n))
                if iteration:
                    rng.shuffle(order)
                point=rng.randrange(1<<n) if iteration else 0
                fixed=sum(1<<v for v in order[k:])
                t=sum(1<<r for r in range(1<<n) if not ((r^point)&fixed) and r!=point)
                if iteration%2:
                    t^=(1<<(1<<n))-1
                actual=measure(n,t)
                if prices is None:
                    prices=actual
                assert actual==prices
                transformed+=1
            split_rows.append(dict(n=n,q=q,k=k,tree=prices[0],dag=prices[1]))
    holdout={}
    for n,cap in ((5,1050),(6,3664)):
        source=here/f"evidence/held-{n}-{cap}-2.json"
        data=json.loads(source.read_text())["witnesses"]
        rows=1<<n
        bound=sum(2*(rows>>s)*(rows-(rows>>s)) for s in range(2,n+1))
        labels=[]
        for w in data:
            t=int(w["truth"],16)
            assert bool(solution(n,t))==(w["cost"]<=bound)
            if w["cost"]<=bound:
                measure(n,t,w["cost"])
                labels.append(w["rep"])
        assert len(labels)==n
        holdout[n]=labels
    native={}
    for t in (0x0001,0x0007,0xfff8,0x007f,0x01fe):
        answer=solution(4,t)
        assert answer
        for ep in answer["endpoints"]:
            goal=ep["objective"] if ep["objective"]!="both" else "activity"
            native[f"{t:04x}/{goal}"]=abc(args.abc,4,t,answer,goal)
    # Outside the theorem, the wrapper dispatches to the author's ordinary search.
    assert solution(4,6) is None
    fallback=abc(args.abc,4,6,None,"activity")
    assert "Switching Activity=208" in fallback and "FF_ORIGINAL_CNF verified" not in fallback
    report=dict(all_four_tables=65536,recognized_four=dict(counts),independent_tree_cases=transformed,
                splits=split_rows,heldout_labels=holdout,native=native,native_outside_fallback=fallback,
                total_wall_s=time.perf_counter()-start)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(dict(four=counts,transformed=transformed,heldout=holdout,native=len(native),
               wall_s=report["total_wall_s"]))


if __name__=="__main__":
    main()
