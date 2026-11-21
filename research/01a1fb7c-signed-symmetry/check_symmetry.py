"""Check phase-normalized circuit orbits independently of the ABC integration."""
from functools import cache
from itertools import combinations, permutations, product
from pathlib import Path
from zipfile import ZipFile
import json
import re

HERE = Path(__file__).resolve().parent
MASK = 65535
PINS = tuple(sum((r >> k & 1) << r for r in range(16)) for k in range(4))
OPS = (2, 4, 6, 8, 14)
GATE = re.compile(r"^(\d+) = 4'b([01]{4})\(\s+(\w+)\s+(\w+)\s+\)$", re.M)


def norm(x):
    return x ^ (MASK if x & 1 else 0)


def gate(code, a, b):
    value = 0
    for v in range(4):
        if code >> v & 1:
            value |= (a if v & 2 else MASK ^ a) & (b if v & 1 else MASK ^ b)
    return value


FIRST = {gate(op, PINS[i], PINS[j]) for i,j in combinations(range(4), 2) for op in OPS}
assert len(FIRST) == 30


def maps():
    for perm in permutations(range(4)):
        base = [sum(((r >> perm[j]) & 1) << j for j in range(4)) for r in range(16)]
        for phase in range(16):
            yield phase, tuple(v ^ phase for v in base)


MAPS = tuple(maps())


def transform(tt, rows):
    return norm(sum(((tt >> source) & 1) << k for k,source in enumerate(rows)))


@cache
def stabilizer(target):
    return [(ph,rows) for ph,rows in MAPS if transform(target,rows) == norm(target)]


def leaders(target, signed):
    group = [rows for ph,rows in stabilizer(target) if signed or not ph]
    canonical = {v: min(transform(v,rows) for rows in group) for v in FIRST}
    assert all(k in FIRST and canonical[k] == k for k in canonical.values())
    return set(canonical.values())


def weight(g):
    q = g.bit_count()
    return 2*q*(16-q)


def check_witness(record):
    target = int(record["witness"]["truth"], 16)
    activity = record["witness"]["activity"]
    signals = dict(zip("abcd",PINS))
    gates = sorted(GATE.findall(record["solver_output"].replace("\r","")), key=lambda row:int(row[0]))
    for idx, (name, code, a, b) in enumerate(gates):
        raw = int(code,2)
        if idx+1 == len(gates) and target & 1:
            raw ^= 15
        assert raw in OPS
        signals[name] = gate(raw, signals[a], signals[b])
    assert signals[gates[-1][0]] == norm(target)
    assert sum(weight(signals[name]) for name,*_ in gates[:-1]) == activity
    representative = min(transform(signals[gates[0][0]],rows) for _,rows in stabilizer(target))
    found = False
    for _,rows in stabilizer(target):
        changed = {name:transform(tt,rows) for name,tt in signals.items()}
        assert set(changed[key] for key in "abcd") == set(PINS)
        for name, _, a, b in gates:
            assert any(gate(op,changed[a],changed[b]) == changed[name] for op in OPS)
            assert weight(changed[name]) == weight(signals[name])
        assert changed[gates[-1][0]] == norm(target)
        found |= changed[gates[0][0]] == representative
    assert found
    return len(stabilizer(target))


if __name__ == "__main__":
    samples = {}
    for target in (0x0189,0x07b4):
        group = stabilizer(target)
        samples[f"{target:04x}"] = dict(unsigned_transforms=sum(not ph for ph,_ in group),
                                        signed_transforms=len(group), all_first=30,
                                        unsigned_first=len(leaders(target,False)),
                                        signed_first=len(leaders(target,True)))
    # Check closure even for all four independent assignments to two incoming phases.
    for op, pa, pb in product(OPS,range(2),range(2)):
        raw = gate(op, PINS[0] ^ (MASK*pa), PINS[1] ^ (MASK*pb))
        assert norm(raw) in {gate(f,PINS[0],PINS[1]) for f in OPS}
    checked, transforms = 0, 0
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        for group in ("author","support","both"):
            for line in z.read("evidence/e14-main/"+group+".jsonl").splitlines():
                row = json.loads(line)
                if "witness" in row:
                    transforms += check_witness(row)
                    checked += 1
    print(json.dumps(dict(pilots=samples, checked_circuits=checked, transformed_circuits=transforms,
                          primitive_phase_combinations=20), indent=2))
