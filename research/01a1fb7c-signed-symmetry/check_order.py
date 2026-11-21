"""Check compatibility of the two symmetry orders on every archived circuit."""
from functools import cache
from hashlib import sha256
from itertools import combinations
import json
from zipfile import ZipFile
from check_symmetry import HERE, FIRST, GATE, MASK, OPS, PINS, gate, leaders, stabilizer, transform

KEYS = {gate(op,PINS[i],PINS[j]):(i,j,gate(op,PINS[i],PINS[j]))
        for i,j in combinations(range(4),2) for op in OPS}
assert set(KEYS) == FIRST


@cache
def swaps(target):
    pairs = []
    for i,j in combinations(range(4),2):
        rows = [r ^ ((1<<i)|(1<<j)) if ((r>>i)^(r>>j))&1 else r for r in range(16)]
        if all((target>>r & 1)==(target>>s & 1) for r,s in enumerate(rows)):
            pairs.append((i,j))
    return pairs


def compatible(record):
    target = int(record["witness"]["truth"],16)
    gates = sorted(GATE.findall(record["solver_output"].replace("\r","")),key=lambda r:int(r[0]))
    first_at = {}
    for pos,(_,_,a,b) in enumerate(gates):
        for pin in (a,b):
            if pin in "abcd":
                first_at.setdefault(pin,pos)
    _,code,a,b = gates[0]
    h = gate(int(code,2),PINS["abcd".index(a)],PINS["abcd".index(b)])
    transforms = stabilizer(target)
    best = min(KEYS[transform(h,rows)] for _,rows in transforms)
    for _,rows in transforms:
        if KEYS[transform(h,rows)] != best:
            continue
        order = {PINS.index(transform(PINS[i],rows)):first_at[pin] for i,pin in enumerate("abcd")}
        if all(order[p]<=order[q] for p,q in swaps(target)):
            return True
    return False


def main():
    groups = {}
    count = 0
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        for name in ("author","support","both"):
            for ln in z.read(f"evidence/e14-main/{name}.jsonl").splitlines():
                row = json.loads(ln)
                if "witness" in row:
                    assert compatible(row), row["witness"]
                    count += 1
                truth = row["experiment"]["truth"]
                if name!="both" or truth in ("0189","07b4"):
                    continue
                target = int(truth,16)
                advantage = len(leaders(target,True))<len(leaders(target,False))
                difficulty = ("timeout" if row["status"]=="timeout" else
                              "fast" if row["wall_s"]<=10 else "medium")
                groups.setdefault((difficulty,advantage),[]).append(truth)
    cohort = []
    for (diff,adv),entries in sorted(groups.items()):
        selected = min(entries,key=lambda t:sha256(("01a1fb7c-v1:"+t).encode()).digest())
        cohort.append(dict(difficulty=diff,signed_stricter=adv,cell_size=len(entries),truth=selected))
    return dict(witnesses_with_compatible_representative=count,cohort=cohort)


if __name__=="__main__":
    print(json.dumps(main(),indent=2))
