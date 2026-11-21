"""Check known full circuits against prefix prices and construct surviving symmetric witnesses."""
from collections import Counter
from functools import cache
from itertools import permutations
import json
from pathlib import Path
import re
from probe_prefix_budget import projected_bound, PINS
from witness import GATE, simulate

ROOT=Path(__file__).resolve().parents[1]
PERMS=list(permutations(range(4)))
ROWS={p:[sum((r>>i&1)<<v for i,v in enumerate(p)) for r in range(16)] for p in PERMS}


def permute(f,p):
    return sum((f>>r&1)<<i for i,r in enumerate(ROWS[p]))


@cache
def stabilizer(t):
    return [p for p in PERMS if permute(t,p)==t]


def relabel(log,t,p,score):
    text=log.replace("\r","")
    gates=GATE.findall(text)
    out=[f"Realization of given 4-input function using {len(gates)} two-input gates complementary={t&1}:"]
    def rename(s):
        return chr(97+p.index(ord(s)-97)) if s in "abcd" and len(s)==1 else s
    def num(s):
        return ord(s)-97 if len(s)==1 and s in "abcd" else int(s)
    for i,bits,left,right in gates:
        x,y=rename(left),rename(right)
        op=int(bits,2)
        if num(x)>num(y):
            x,y=y,x
            op=(op&9)|((op&2)<<1)|((op&4)>>1)
        out.append(f"{i} = 4'b{op:04b}( {x} {y} )")
    out.append(f"Switching Activity={score}")
    return simulate("\n".join(out),4,t)


def run():
    counts=Counter()
    classes=set()
    for role in ("author","support","both"):
        for line in (ROOT/f"evidence/e14-main/{role}.jsonl").read_text().splitlines():
            row=json.loads(line)
            if "witness" not in row:
                continue
            w=row["witness"]
            t=int(w["truth"],16)
            score=w["activity"]
            log=row["solver_output"]
            assert simulate(log,4,t)==w
            signals={int(i):sum(int(b)<<k for k,b in enumerate(s)) for i,s in
                     re.findall(r"^i=(\d+):([01]{16})",log,re.M)}
            if w["gates"]>=3:
                for mu in (0,20):
                    lb=projected_bound(t,(signals[4],signals[5]),mu,w["gates"]-3)
                    assert lb<=score, (w,mu,lb)
                counts["prefix_checked"]+=1
            perms=stabilizer(t)
            p=min(perms,key=lambda p:permute(signals[4],p))
            normalized=permute(signals[4],p)
            assert normalized==min(permute(normalized,q) for q in perms)
            assert relabel(log,t,p,score)==w
            counts["symmetry_checked"]+=1
            counts["witness_required_relabel"]+=normalized!=signals[4]
            classes.add(t)
    return dict(classes=len(classes),checks=counts,violations=0)


if __name__=="__main__":
    print(json.dumps(run(),indent=2))
