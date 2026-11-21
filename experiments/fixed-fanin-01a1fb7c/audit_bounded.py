"""Independently check bounded search, complete witnesses, equality and unknown outcomes."""
import argparse
import itertools
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
PRIMARY = [0xaaaa, 0xcccc, 0xf0f0, 0xff00]


def replay(row):
    wires = list(PRIMARY)
    cost = 0
    for i, (hi, lo, op) in enumerate(row["chain"]):
        assert 0 <= lo < hi < len(wires) and op in (2, 4, 6, 8, 14)
        out = 0
        for r in range(16):
            bit = ((wires[hi] >> r) & 1) + 2 * ((wires[lo] >> r) & 1)
            out |= ((op >> bit) & 1) << r
        wires.append(out)
        if i + 1 < len(row["chain"]):
            cost += 2 * out.bit_count() * (16 - out.bit_count())
    given = int(row["truth"], 16)
    assert wires[-1] == (given ^ (65535 if given & 1 else 0))
    assert cost == row["cost"] <= row["cap"]


def small_oracle(cap):
    """Enumerate unordered reachable sets, with neither symmetry ordering nor cofactor bounds."""
    minima = {}
    stack = [(frozenset(PRIMARY), 0)]
    visited = set()
    while stack:
        wires, paid = stack.pop()
        if wires in visited:
            continue
        visited.add(wires)
        outputs = set()
        for x, y in itertools.combinations(wires, 2):
            outputs.update((x & ~y, y & ~x, x & y, x | y, x ^ y))
        for g in outputs:
            minima[g] = min(paid, minima.get(g, paid))
            next_cost = paid + 2 * g.bit_count() * (16 - g.bit_count())
            if g and g not in wires and next_cost <= cap:
                stack.append((wires | {g}, next_cost))
    return minima, len(visited)


def audit(binary, outfile):
    with ZipFile(HERE / "reproduction.zip") as archive:
        records = [json.loads(line) for arm in ("author", "support", "both")
                   for line in archive.read(f"evidence/e14-main/{arm}.jsonl").splitlines()]
    cases = sorted({r["experiment"]["truth"] for r in records})
    known = {r["witness"]["truth"]:r["witness"]["activity"] for r in records if "witness" in r}
    small, states = small_oracle(240)
    checks = [(t, 240, 2000000, arm) for t in cases for arm in (0, 1)]
    checks += [(t, cap, 2000000, arm) for t, opt in (("0189",304),("0019",310),("0198",352))
               for cap in (opt-2, opt, 360) for arm in (0, 1)]
    checks += [("0189", 360, 1, arm) for arm in (0, 1)]
    data = "\n".join(f"{t} {c} {w} {a}" for t,c,w,a in checks)
    output = subprocess.run([binary], input=data, text=True, capture_output=True, check=True)
    rows = list(map(json.loads, output.stdout.splitlines()))
    for row, (t, cap, work, arm) in zip(rows, checks, strict=True):
        assert (row["truth"], row["cap"], row["work"], row["projected"]) == (t, cap, work, arm)
        if work == 1:
            assert not row["complete"] and row["visited"] == 1
            continue
        assert row["complete"]
        norm = int(t, 16)
        norm ^= 65535 if norm & 1 else 0
        optimum = small.get(norm, 241) if cap == 240 else known[t]
        assert bool(row["found"]) == (optimum <= cap)
        if row["found"]:
            replay(row)
            assert row["cost"] == optimum
    outfile.write_text(json.dumps(dict(small_budget=240, independent_states=states,
                                       checked=len(rows), checks=rows), separators=(",", ":")) + "\n")
    print(len(rows), states)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("binary", type=Path)
    p.add_argument("out", type=Path)
    args = p.parse_args()
    audit(str(args.binary.resolve()), args.out)
