"""Check activity bounds conditional on the first signal and the shared output operator."""
from argparse import ArgumentParser
from functools import cache
from itertools import combinations
import json
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile

from check_chain import least_rank, rank
from check_symmetry import FIRST, GATE, HERE, OPS, PINS, gate, norm, weight
from restriction import INPUTS, LIMIT, PARTS, bound, operations, project, reachable_tables, table

# Either order of the two unrestricted local output pins is permitted.
KINDS = (2,6,8,14)


@cache
def projected_codes(op, phase, contains_zero):
    options = set()
    for a_phase in (0,1):
        for b_phase in (0,1):
            if contains_zero and (a_phase or b_phase):
                continue
            flip = 2*a_phase+b_phase
            if (op>>flip)&1 != phase:
                continue
            code = sum((((op>>(x^flip))&1)^phase)<<x for x in range(4))
            options.add(KINDS.index(2 if code==4 else code))
    assert options
    return tuple(sorted(options))


@cache
def costs(free):
    init = tuple(sorted({*INPUTS,free}))
    seen = {init}
    stack = [(init,0)]
    minima = [[[255 if k<4 else LIMIT+2]*128 for _ in KINDS] for k in range(5)]
    while stack:
        state, cost = stack.pop()
        depth = len(state)-len(init)
        ds = (depth,4) if depth<4 else (4,)
        # Equal or constant projected fanins can realize a direct wire or constant.
        signed_and, xor, plain_and, plain_or = (set(state),set(state),set(state),set(state))
        for a,b in combinations(state,2):
            ab,ba,x,both,either = operations(a,b)
            signed_and.update((ab,ba))
            xor.add(x)
            plain_and.add(both)
            plain_or.add(either)
        ends = (signed_and,xor,plain_and,plain_or)
        for k in ds:
            for row,values in zip(minima[k],ends):
                for x in values:
                    i=x//2
                    if cost<row[i]:
                        row[i]=cost
        for x in set.union(*ends).difference(state):
            ones = x.bit_count()
            after = cost+2*ones*(8-ones)
            if after<=LIMIT or depth<3:
                nxt=tuple(sorted((*state,x)))
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append((nxt,after))
    for k in (1,2,3):
        for i in range(len(KINDS)):
            minima[k][i]=list(map(min,minima[k][i],minima[k-1][i]))
    return minima


@cache
def endpoint_bound(t,first,depth,op):
    t=norm(t)
    best=0
    for pair in PARTS:
        total=0
        for side,rows in enumerate(pair):
            f = project(first,rows)
            choices = costs(0 if f in INPUTS else f)[min(depth,4)]
            index = project(t,rows)//2
            phase = (t>>rows[0])&1
            total += min(choices[i][index] for i in projected_codes(op,phase,side==0))
        best=max(best,total)
    return weight(first)+2*best


def audit():
    start=perf_counter()
    for free in reachable_tables():
        for k,reference in enumerate(table(free)):
            assert list(map(min,zip(*costs(free)[k])))==reference
    generation=perf_counter()-start
    slack=[]
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        for method in ("author","support","both"):
            for line in z.read(f"evidence/e14-main/{method}.jsonl").splitlines():
                rec=json.loads(line)
                if "witness" not in rec:
                    continue
                w=rec["witness"]
                t=int(w["truth"],16)
                gates=sorted(GATE.findall(rec["solver_output"].replace("\r","")),key=lambda g:int(g[0]))
                _,code,a,b=gates[0]
                pins=dict(zip("abcd",PINS))
                first=gate(int(code,2),pins[a],pins[b])
                op=int(gates[-1][1],2) ^ (15 if t&1 else 0)
                low=endpoint_bound(t,first,len(gates)-2,op)
                assert low<=w["activity"],(t,first,op,low,w)
                slack.append(w["activity"]-low)
    cases={}
    for name in ("0189","03dd"):
        t=int(name,16)
        reps=sorted(g for g in FIRST if rank(g)==least_rank(t,g))
        queries=[]
        for q in json.loads((HERE/f"search-effort-{name}.json").read_text())[-1]["queries"]:
            budget=q["bound"]
            k=q["gates"]-2
            pairs={(g,op) for g in reps if bound(t,g,k)<=budget for op in OPS}
            admitted={(g,op) for g,op in pairs if endpoint_bound(t,g,k,op)<=budget}
            separate=sum(1 for g,op in pairs if g in {a for a,_ in admitted} and op in {b for _,b in admitted})
            queries.append(dict(gates=q["gates"],budget=budget,conflicts=q["conflicts"],base_pairs=len(pairs),
                                separate_pairs=separate,joint_pairs=len(admitted)))
        cases[name]=dict(changed=sum(x["base_pairs"]>x["joint_pairs"] for x in queries),
                         strictly_joint=sum(x["separate_pairs"]>x["joint_pairs"] for x in queries),
                         most_conflicts=sorted(queries,key=lambda x:-x["conflicts"])[:5],queries=queries)
    return dict(generation_and_table_check_s=generation,checked_witnesses=len(slack),minimum_slack=min(slack),
                reduced_to_original_cells=16*5*128,cases=cases)


if __name__=="__main__":
    p=ArgumentParser()
    p.add_argument("--header",type=Path)
    args=p.parse_args()
    if args.header:
        lines=["/* Small-function endpoint costs generated for all targets by endpoint.py. */",
               "static const unsigned char endpoint_cost[][5][4][128] = {"]
        for free in reachable_tables():
            lines.append("  {")
            for rows in costs(free):
                lines.append("    {")
                lines.extend("      {"+",".join(map(str,row))+"}," for row in rows)
                lines.append("    },")
            lines.append("  },")
        args.header.write_text("\n".join([*lines,"};",""]),encoding="utf-8",newline="\n")
    else:
        print(json.dumps(audit(),indent=2))
