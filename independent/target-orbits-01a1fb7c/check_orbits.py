"""Check target stabilizers independently of ABC and reconstruct transformed gate networks."""
from functools import cache
from itertools import combinations, permutations
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
OPS = (2, 4, 6, 8, 14)
GATE = re.compile(r"^(\d+) = 4'b([01]{4})\(\s+(\w+)\s+(\w+)\s+\)", re.M)


def pins(n):
    return [sum((r >> i & 1) << r for r in range(1 << n)) for i in range(n)]


def op(code, a, b):
    # The printed first operand is the more significant operator input.
    return {2: b & ~a, 4: a & ~b, 6: a ^ b, 8: a & b, 14: a | b}[code]


def normal(t, mask):
    return t ^ (mask if t & 1 else 0)


@cache
def transforms(n):
    result = []
    for p in permutations(range(n)):
        perm = [sum((r >> j & 1) << i for i,j in enumerate(p)) for r in range(1 << n)]
        for phase in range(1 << n):
            result.append((phase,tuple(r ^ phase for r in perm)))
    return result


@cache
def image(t, rows):
    return sum((t >> r & 1) << j for j,r in enumerate(rows))


@cache
def group(n, target, signed=True):
    mask = (1 << (1 << n))-1
    return tuple(r for s,r in transforms(n) if (signed or s == 0) and
                 normal(image(target,r),mask) == normal(target,mask))


@cache
def representatives(n, target, signed=True):
    mask = (1 << (1 << n))-1
    first = {op(c,a,b) for a,b in combinations(pins(n),2) for c in OPS}
    return {h for h in first if h == min(normal(image(h,r),mask) for r in group(n,target,signed))}


def check_enumeration():
    n, rows = 3, 8
    base, reduced = set(), set()
    tested = 0
    def visit(wires, counts, first):
        nonlocal tested
        for i,j in combinations(range(len(wires)),2):
            for code in OPS:
                t = op(code,wires[i],wires[j])
                h = t if first is None else first
                tested += 1
                signature = (t,tuple(counts))
                base.add(signature)
                if h in representatives(n,t):
                    reduced.add(signature)
                if len(counts) < 2:
                    visit(wires+[t], counts+[min(t.bit_count(),rows-t.bit_count())],h)
    visit(pins(n),[],None)
    assert base == reduced, base-reduced
    return dict(circuits=tested, target_and_ordered_count_profiles=len(base))


def check_witness(text, target, expected):
    lines = sorted((int(i),int(c,2),a,b) for i,c,a,b in GATE.findall(text))
    signals = dict(zip("abcd",pins(4)))
    gates = []
    for i,code,a,b in lines:
        if i == lines[-1][0] and target & 1:
            code ^= 15
        t = op(code,signals[a],signals[b])
        signals[f"{i:02d}"] = t
        gates.append((code,a,b,t))
    assert gates[-1][3] == normal(target,65535)
    mapped = 0
    for rows in group(4,target):
        values = {key: normal(image(signals[key],rows),65535) for key in "abcd"}
        assert set(values.values()) == set(pins(4))
        cost = 0
        for (code,a,b,t),(i,*_) in zip(gates,lines):
            aphase, bphase = (signals[a] >> rows[0]) & 1, (signals[b] >> rows[0]) & 1
            outphase = (t >> rows[0]) & 1
            new = sum((((code >> (((v >> 1 ^ aphase)<<1) | ((v & 1)^bphase))) & 1) ^ outphase)
                      << v for v in range(4))
            assert new in OPS and (new == 6) == (code == 6)
            remapped = op(new,values[a],values[b])
            assert remapped == normal(image(t,rows),65535)
            assert min(t.bit_count(),16-t.bit_count()) == min(remapped.bit_count(),16-remapped.bit_count())
            values[f"{i:02d}"] = remapped
            if i != lines[-1][0]:
                cost += 2 * remapped.bit_count() * (16-remapped.bit_count())
        assert cost == expected and values[f"{lines[-1][0]:02d}"] == normal(target,65535)
        mapped += values["04"] in representatives(4,target)
    assert mapped
    return len(group(4,target))


def main():
    origin = HERE / "reproduction/evidence"
    family = json.loads((origin / "npn-family.json").read_text())["essential"]
    stats = {t:dict(group=len(group(4,int(t,16))),plain=len(representatives(4,int(t,16),False)),
                    signed=len(representatives(4,int(t,16)))) for t in family}
    witnesses = images = 0
    for arm in ("author","support","both"):
        for line in (origin / f"e14-main/{arm}.jsonl").read_text().splitlines():
            row = json.loads(line)
            if "witness" in row:
                images += check_witness(row["solver_output"],int(row["witness"]["truth"],16),row["witness"]["activity"])
                witnesses += 1
    trivial = next((t for t in family if stats[t]["group"] == 1),None)
    return dict(three_inputs=check_enumeration(), witnesses=witnesses, transformed_witnesses=images,
                first_trivial=trivial, inputs_with_reductions=sum(d["signed"]<30 for d in stats.values()),
                signed_strictly_stronger=sum(d["signed"]<d["plain"] for d in stats.values()), family=stats)


if __name__ == "__main__":
    print(json.dumps(main(),indent=2))
