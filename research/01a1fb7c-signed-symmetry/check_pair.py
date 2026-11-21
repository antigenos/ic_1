"""Compare prefix canonicalization under target permutations and a legal step swap."""
from functools import cache
from itertools import product
import json
from zipfile import ZipFile
from check_order import KEYS, compatible, swaps
from check_symmetry import HERE, FIRST, GATE, PINS, gate, stabilizer, transform


@cache
def images(target,h):
    return tuple(transform(h,rows) for _,rows in stabilizer(target))


@cache
def least(target,h):
    return min(KEYS[v] for v in images(target,h))


def compare_prefixes(target):
    counts = dict(sorted=0,separate=0,mixed=0,full_orbit=0)
    example = None
    for a,b in product(sorted(FIRST),repeat=2):
        ka,kb=KEYS[a],KEYS[b]
        if ka>kb:
            continue
        counts["sorted"] += 1
        if ka!=least(target,a):
            continue
        counts["separate"] += 1
        if ka>least(target,b):
            if example is None:
                example=dict(first=f"{a:04x}",second=f"{b:04x}",permuted_second=f"{least(target,b)[2]:04x}")
            continue
        counts["mixed"] += 1
        best=min(tuple(sorted((KEYS[x],KEYS[y]))) for x,y in zip(images(target,a),images(target,b)))
        counts["full_orbit"] += (ka,kb)==best
    return dict(syntactic=900,**counts,strict_example=example)


def audit(record):
    target=int(record["witness"]["truth"],16)
    gates=sorted(GATE.findall(record["solver_output"].replace("\r","")),key=lambda r:int(r[0]))
    if len(gates)<3 or any(pin not in ("a","b","c","d") for pin in gates[1][2:]):
        assert compatible(record)
        return False
    h=[]
    for _,op,a,b in gates[:2]:
        h.append(gate(int(op,2),PINS["abcd".index(a)],PINS["abcd".index(b)]))
    best=min(tuple(sorted((KEYS[x],KEYS[y]))) for x,y in zip(images(target,h[0]),images(target,h[1])))
    for _,rows in stabilizer(target):
        for first,second in ((0,1),(1,0)):
            signature=tuple(KEYS[transform(h[i],rows)] for i in (first,second))
            if signature!=best:
                continue
            assert signature[0]<=least(target,h[second])
            order={}
            for i,g in enumerate([gates[first],gates[second],*gates[2:]]):
                for pin in g[2:]:
                    if pin in ("a","b","c","d"):
                        order.setdefault(PINS.index(transform(PINS["abcd".index(pin)],rows)),i)
            if all(order[a]<=order[b] for a,b in swaps(target)):
                return True
    raise AssertionError((target,h))


if __name__=="__main__":
    total=independent=0
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        for arm in ("author","support","both"):
            for line in z.read(f"evidence/e14-main/{arm}.jsonl").splitlines():
                row=json.loads(line)
                if "witness" in row:
                    independent+=audit(row)
                    total+=1
    print(json.dumps(dict(cases={f"{t:04x}":compare_prefixes(t) for t in (0x0189,0x07b4)},
                          witnesses=total,reorderable_witness_prefixes=independent),indent=2))
