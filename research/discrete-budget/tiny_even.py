"""All 3-input, 2-paid-gate circuits plus a free output; test an even hole in a SAT window."""
import json
from itertools import combinations


def successors(left,right):
    return (left&~right, right&~left, left^right, left&right, left|right)


def charge(signal):
    ones=signal.bit_count()
    return 2*ones*(8-ones)


def main():
    primary=(0xaa,0xcc,0xf0)
    target=0x02
    witnesses,branch={},{}
    count=0
    for a,b in combinations(range(3),2):
        for op,g in enumerate(successors(primary[a],primary[b])):
            first=primary+(g,)
            for c,d in combinations(range(4),2):
                for op2,j in enumerate(successors(first[c],first[d])):
                    nodes=first+(j,)
                    for e,f in combinations(range(5),2):
                        if {a,b,c,d,e,f}!=set(range(5)):
                            continue
                        for output,t in enumerate(successors(nodes[e],nodes[f])):
                            if t!=target or j==0:
                                continue
                            count+=1
                            cost=charge(g)+charge(j)
                            witness=dict(cost=cost,
                                net=[[a,b,op],[c,d,op2],[e,f,output]],
                                truths=[hex(g),hex(j),hex(t)])
                            # Prefer a witness with distinct nonconstant internal signals.
                            if cost not in witnesses or j not in first:
                                witnesses[cost]=witness
                            if (e,f,output)==(0,4,0) and min(j.bit_count(),8-j.bit_count())==2:
                                if cost not in branch or j not in first:
                                    branch[cost]=witness
    assert sorted(branch)==[48,56] and 54 in witnesses
    assert not any(57<=v<=62 for v in branch)
    print(json.dumps(dict(inputs=3,target="02",paid_gates=2,free_output=True,
        operation_order=["x & ~y","y & ~x","x XOR y","x AND y","x OR y"],
        enumerated_target_realizations=count,
        branch="Output x0 & ~j, with second paid gate j of folded count 2",
        hull=[48,56],branch_costs=branch,window_54_global_witness=witnesses[54],
        interval_sufficient_window=[57,62],hit_window=[48,48]),indent=2))


if __name__=="__main__":
    main()
