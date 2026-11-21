"""Finite three-input cost relaxation and a check on archived four-input circuits."""
from argparse import ArgumentParser
from functools import cache
from itertools import combinations
import json
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile

from check_chain import least_rank, rank
from check_symmetry import FIRST, GATE, HERE, PINS, gate, weight


LIMIT = 76
INPUTS = (0, 0xaa, 0xcc, 0xf0)


def normal8(x):
    return x ^ (255 if x & 1 else 0)


def partitions():
    # Eliminate the highest set coordinate, retaining the three other input wires.
    for bits in range(1, 16):
        if bits.bit_count() > 2:
            continue
        pivot = bits.bit_length() - 1
        low = (1 << pivot) - 1
        pair = [[], []]
        for i in range(8):
            r = (i & low) | ((i & ~low) << 1)
            for phase, rows in enumerate(pair):
                rows.append(r | ((((r & bits).bit_count() + phase) & 1) << pivot))
        assert sorted(pair[0]+pair[1]) == list(range(16))
        yield tuple(map(tuple, pair))


PARTS = tuple(partitions())


@cache
def project(x, rows):
    return normal8(sum(((x >> r) & 1) << i for i, r in enumerate(rows)))


@cache
def operations(a, b):
    return a & ~b, b & ~a, a ^ b, a & b, a | b


@cache
def table(free):
    # Repeated normalized signals may use the earlier wire, which only lowers cost.
    initial = tuple(sorted({*INPUTS, free}))
    seen = {initial}
    stack = [(initial, 0)]
    minima = [LIMIT+2]*128  # all costs are even
    while stack:
        signals, cost = stack.pop()
        outputs = set(signals)
        for a, b in combinations(signals, 2):
            outputs.update(operations(a, b))
        for x in outputs:
            minima[x//2] = min(minima[x//2], cost)
        for x in outputs.difference(signals):
            k = x.bit_count()
            new_cost = cost + 2*k*(8-k)
            if new_cost <= LIMIT:
                nxt = tuple(sorted((*signals, x)))
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append((nxt, new_cost))
    return minima


def residual(target, free, rows):
    f = project(free, rows)
    return table(0 if f in INPUTS else f)[project(target, rows)//2]


@cache
def bound(target, first):
    return weight(first) + 2*max(sum(residual(target, first, r) for r in pair) for pair in PARTS)


def reachable_tables():
    free = {project(g, r) for g in FIRST for pair in PARTS for r in pair}
    assert all(project(p,r) in INPUTS for p in PINS for pair in PARTS for r in pair)
    return sorted({0, *(x for x in free if x not in INPUTS)})


def audit():
    from lower_bound import cheaper_circuit
    for a in range(9):
        for b in range(9):
            assert 2*(a+b)*(16-a-b) == 4*(a*(8-a)+b*(8-b)) + 2*(a-b)**2
    started = perf_counter()
    free = reachable_tables()
    for g in free:
        table(g)
    generation = perf_counter() - started
    for t in range(0, 256, 2):
        lb = table(0)[t//2]
        assert not cheaper_circuit(3,t,lb)[0]
        if lb <= LIMIT:
            assert cheaper_circuit(3,t,lb+1)[0]
    verified = []
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        for k in ("author","support","both"):
            for line in z.read(f"evidence/e14-main/{k}.jsonl").splitlines():
                row = json.loads(line)
                if "witness" not in row:
                    continue
                t = int(row["witness"]["truth"], 16)
                gates = sorted(GATE.findall(row["solver_output"].replace("\r","")), key=lambda g:int(g[0]))
                _, op, a, b = gates[0]
                pins = dict(zip("abcd", PINS))
                first = gate(int(op, 2), pins[a], pins[b])
                lower = bound(t, first)
                optimum = row["witness"]["activity"]
                assert lower <= optimum
                verified.append(optimum-lower)
    cases = {}
    for target in ("0189", "03dd"):
        t = int(target, 16)
        keep = {g: bound(t,g) for g in FIRST if rank(g) == least_rank(t,g)}
        profile = json.loads((HERE/f"search-effort-{target}.json").read_text())[-1]
        assert profile["mode"] == "chain-first"
        rows = [dict(gates=q["gates"], budget=q["bound"], remaining=sum(v<=q["bound"] for v in keep.values()),
                     conflicts=q["conflicts"]) for q in profile["queries"]]
        cases[target] = dict(choices=len(keep),bounds={f"{g:04x}":v for g,v in sorted(keep.items())},
                             whole_queries_removed=sum(r["remaining"]==0 for r in rows),
                             removed_query_conflicts=sum(r["conflicts"] for r in rows if r["remaining"]==0),
                             queries=rows)
    return dict(limit=LIMIT, tables=len(free), generation_s=generation, standalone_functions_checked=128,
                checked_archived_circuits=len(verified), minimum_observed_slack=min(verified), cases=cases)


if __name__ == "__main__":
    p = ArgumentParser()
    p.add_argument("--header",type=Path)
    args = p.parse_args()
    if args.header:
        indices = reachable_tables()
        lut = {g:i for i,g in enumerate(indices)}
        cats = [lut.get(i*2,0) for i in range(128)]
        lines = ["/* Generated by restriction.py from the five normalized operators. */",
                 "static const unsigned char restriction_free[128] = {"+",".join(map(str,cats))+"};",
                 "static const unsigned char restriction_cost[][128] = {"]
        lines.extend("    {"+",".join(map(str,table(g)))+"}," for g in indices)
        args.header.write_text("\n".join([*lines,"};",""]), encoding="utf-8", newline="\n")
    else:
        print(json.dumps(audit(), indent=2))
