"""Check conditional residual costs and prefix bounds against independent evidence."""
import argparse
import itertools
import json
from pathlib import Path
import random
import subprocess
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent


def can_reach(target, a, b, budget):
    free = frozenset((0, 0xaa, 0xcc, 0xf0, a, b))
    seen = {free}
    todo = [(free, 0)]
    while todo:
        wires, paid = todo.pop()
        outputs = set(wires)
        for x, y in itertools.combinations(wires, 2):
            outputs.update((x ^ y, x | y, x & y, x & ~y, y & ~x))
        if target in outputs:
            return True
        for g in outputs - wires:
            cost = paid + 2 * g.bit_count() * (8 - g.bit_count())
            state = wires | {g}
            if cost <= budget and state not in seen:
                seen.add(state)
                todo.append((state, cost))
    return False


def audit(binary):
    with ZipFile(HERE / "reproduction.zip") as z:
        records = [json.loads(line) for arm in ("author", "support", "both")
                   for line in z.read(f"evidence/e14-main/{arm}.jsonl").splitlines()]
    cases = sorted({r["experiment"]["truth"] for r in records} |
                   {"0000", "ffff", "ff00", "00ff", "aaaa", "5555"})
    lines = subprocess.run([binary], input="\n".join(cases), text=True,
                           capture_output=True, check=True).stdout.splitlines()
    bounds = {}
    for line in lines:
        truth, *values = line.split()
        depths = list(map(int, values))
        assert len(depths) == 3 and depths == sorted(depths)
        assert all(v % 2 == 0 for v in depths)
        bounds[truth] = depths
    assert set(bounds) == set(cases)
    for trivial in ("0000", "ffff", "ff00", "00ff", "aaaa", "5555"):
        assert bounds[trivial] == [0, 0, 0]
    for r in records:
        if "witness" in r:
            assert bounds[r["witness"]["truth"]][-1] <= r["witness"]["activity"]
    known = {}
    for r in records:
        if "witness" in r:
            key, activity = r["witness"]["truth"], r["witness"]["activity"]
            assert known.setdefault(key, activity) == activity
    matched = [[t for t in sorted(known) if bounds[t][depth] == known[t]] for depth in range(3)]

    rng = random.Random(189)
    probes = []
    for i in range(256):
        t, a, b = (2 * rng.randrange(128) for _ in range(3))
        if i % 4 == 0: b = a
        if i % 4 == 1: a = 0
        probes.append((t, a, b))
    data = "\n".join(f"{t:x} {a:x} {b:x}" for t, a, b in probes)
    reports = subprocess.run([binary, "residual"], input=data, text=True,
                             capture_output=True, check=True).stdout.splitlines()
    for (t, a, b), raw in zip(probes, reports, strict=True):
        bound = int(raw)
        if bound > 0:
            assert not can_reach(t, a, b, bound - 1)
        extras = {a, b} - {0, 0xaa, 0xcc, 0xf0}
        if len(extras) < 2 or bound <= 42:
            assert can_reach(t, a, b, bound)
    return dict(residual_probes=len(probes), checked_circuits=sum("witness" in r for r in records),
                distinct_witness_targets=len(known), tight_certificates_by_depth=matched, bounds=bounds)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("binary", type=Path)
    p.add_argument("out", type=Path)
    args = p.parse_args()
    result = audit(str(args.binary.resolve()))
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print({k:v for k,v in result.items() if k != "bounds"})
