"""Independent truth-row replay, NPN labeling, and small complete cost oracles."""
from collections import Counter
from functools import lru_cache
from itertools import combinations, permutations
from pathlib import Path
import heapq
import json


def literals(n):
    return tuple(sum(((r >> i) & 1) << r for r in range(1 << n)) for i in range(n))


def full(t, n):
    return all(any(((t >> r) ^ (t >> (r ^ (1 << i)))) & 1
                   for r in range(1 << n)) for i in range(n))


@lru_cache(None)
def maps(n):
    rows = 1 << n
    return [tuple(sum(((r >> p[i]) & 1) << i for i in range(n)) for r in range(rows))
            for p in permutations(range(n))]


@lru_cache(None)
def canonical(t, n):
    # Permute once, then translate all rows by swaps on Python integers.
    rows = 1 << n
    mask = (1 << rows) - 1
    least = mask
    for mapping in maps(n):
        permuted = sum(((t >> source) & 1) << row for row, source in enumerate(mapping))
        translations = [permuted]
        for i, high in enumerate(literals_cached(n)):
            step = 1 << i
            translations += [((x & high) >> step) | ((x & (mask ^ high)) << step)
                             for x in translations]
        least = min(least, min(min(x, mask ^ x) for x in translations))
    return least


literals_cached = lru_cache(None)(literals)


def check_witness(n, item):
    truth = cost = 0
    gates = item["gates"]
    for row in range(1 << n):
        wires = [(row >> i) & 1 for i in range(n)]
        if row == 0:
            ones = [0] * len(gates)
        for k, (a, b, op) in enumerate(gates):
            assert 0 <= a < len(wires) and 0 <= b < len(wires) and a != b
            assert op in {2, 4, 6, 8, 14}
            v = (op >> (wires[a] + 2 * wires[b])) & 1
            wires.append(v)
            ones[k] += v
        truth |= wires[-1] << row
    cost = sum(2 * p * ((1 << n) - p) for p in ones[:-1])
    assert truth == int(item["truth"], 16) and cost == item["cost"] and full(truth, n)
    assert canonical(truth, n) == int(item["rep"], 16)


def three_inputs():
    """Dijkstra on raw paid sets, no output or input symmetries in the search."""
    n, rows, mask = 3, 8, 255
    targets = {x for x in range(0, 256, 2) if full(x, n)}
    todo = [(0, ())]
    seen = {()}
    exact = {}
    while targets:
        cost, paid = heapq.heappop(todo)
        wires = (*literals_cached(n), *paid)
        generated = set()
        for a, b in combinations(wires, 2):
            for op in range(1, 16):
                x = 0
                for row in range(rows):
                    i = ((a >> row) & 1) + 2 * ((b >> row) & 1)
                    x |= ((op >> i) & 1) << row
                generated.add(mask ^ x if x & 1 else x)
        for x in generated:
            if x in targets:
                exact[x] = cost
                targets.remove(x)
            if x and x not in wires:
                child = tuple(sorted((*paid, x)))
                if child not in seen:
                    seen.add(child)
                    ones = x.bit_count()
                    heapq.heappush(todo, (cost + 2 * ones * (rows - ones), child))
    return {canonical(x,n): c for x,c in exact.items()}


def compare_reference(n, cap, observed):
    root = Path(__file__).resolve().parent.parent
    if n == 4:
        source = json.loads((root / "evidence/leaves-690.json").read_text())["circuits"]
        expected = {canonical(int(r["truth"], 16), n):r["activity"] for r in source}
        assert len(expected) == 208
    elif n == 3:
        expected = three_inputs()
    else:
        return
    expected = {key: c for key, c in expected.items() if c <= cap}
    if expected != observed:
        diff = [(hex(rep), expected.get(rep), observed.get(rep))
                for rep in sorted(expected.keys() | observed.keys())
                if expected.get(rep) != observed.get(rep)]
        raise ValueError(f"incorrect optimum table: {diff[:12]}")
