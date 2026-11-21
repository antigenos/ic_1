"""Construct actual topologically reordered circuits satisfying the whole-chain control."""
from functools import cache
import json
from zipfile import ZipFile
from check_order import KEYS, swaps
from check_pair import images
from check_symmetry import HERE, MASK, OPS, PINS, GATE, gate, norm, stabilizer, transform, weight


def rank(h):
    lo,hi,_=KEYS[h]
    return hi,lo,h


@cache
def least_rank(t,h):
    return min(map(rank,images(t,h)))


def audit_witness(row):
    t=int(row["witness"]["truth"],16)
    gates=sorted(GATE.findall(row["solver_output"].replace("\r","")),key=lambda g:int(g[0]))
    original=dict(zip("abcd",PINS))
    for idx,(name,code,a,b) in enumerate(gates):
        op=int(code,2) ^ (15 if idx==len(gates)-1 and t&1 else 0)
        original[name]=gate(op,original[a],original[b])
    best=None
    for _,rows in stabilizer(t):
        values={k:transform(v,rows) for k,v in original.items()}
        index={k:PINS.index(values[k]) for k in "abcd"}
        available=list(PINS)
        first_use={}
        sequence=[]
        score=0
        bottom=[]
        for pos in range(len(gates)):
            options=[]
            for name,_,a,b in gates:
                if name not in index and a in index and b in index:
                    hi,lo=sorted([index[a],index[b]],reverse=True)
                    options.append((hi,lo,values[name],name))
            hi,lo,value,name=min(options)
            assert any(gate(op,available[lo],available[hi])==value for op in OPS)
            if sequence:
                assert (hi,lo)>=sequence[-1][:2]
            sequence.append((hi,lo,value))
            for j in (hi,lo):
                if j<4:
                    first_use.setdefault(j,pos)
            if hi<4 and pos<len(gates)-1:
                bottom.append(value)
            index[name]=len(available)
            available.append(value)
            if pos<len(gates)-1:
                score+=weight(value)
        assert name==gates[-1][0] and available[-1]==norm(t) and score==row["witness"]["activity"]
        if best is None or sequence<best[0]:
            best=(sequence,first_use,bottom)
    sequence,first_use,bottom=best
    assert all(first_use[p]<=first_use[q] for p,q in swaps(t))
    assert all(sequence[0]<=least_rank(t,h) for h in bottom)
    return len(bottom)


if __name__=="__main__":
    counts={}
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        for name in ("author","support","both"):
            for line in z.read(f"evidence/e14-main/{name}.jsonl").splitlines():
                row=json.loads(line)
                if "witness" in row:
                    q=audit_witness(row)
                    counts[q]=counts.get(q,0)+1
    print(json.dumps(dict(reconstructed=sum(counts.values()),by_primary_only_gates=counts),indent=2))
