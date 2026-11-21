"""Prove each logged reason from its actual literals with an independent integer-pair row DP."""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path

OPS = (2, 4, 6, 8, 14)


@lru_cache(maxsize=None)
def variable_map(n, gates):
    out = n + gates - 1
    table = {1 + 3 * (gates - 1) + k: ("op", k) for k in range(3)}
    next_var = 1 + 3 * gates
    for obj in range(n, out + 1):
        for pin in (0, 1):
            for pred in range(obj - pin):
                if obj == out:
                    table[next_var] = ("sel", pin, pred)
                next_var += 1
    rows = 1 << n
    for row in range(1, rows):
        for obj in range(n, out + 1):
            if obj < out:
                table[next_var + 2] = ("row", obj, row)
            next_var += 3
    triangular = (rows - 1) * rows // 2
    for obj in range(n, out):
        for count in range(1, rows // 2 + 1):
            v = next_var + triangular + count
            table[v] = ("count", obj, count)
        next_var += triangular + rows // 2 + 1
    return table


@lru_cache(maxsize=20000)
def possible(rows, target, op, zx, ox, zy, oy):
    # Bit (a*(rows+1)+b) denotes a reachable pair of ordinary, unfolded counts.
    width = rows + 1
    states = 1
    for r in range(rows):
        bit = 1 << r
        choices = 0
        for x, y in ((0, 0), (0, 1), (1, 0), (1, 1)):
            if (ox if not x else zx) & bit or (oy if not y else zy) & bit:
                continue
            if (op >> (x + 2*y)) & 1 == (target >> r) & 1:
                choices |= states << (x * width + y)
        states = choices
        if not states:
            break
    folded = set()
    while states:
        bit = states & -states
        a, b = divmod(bit.bit_length() - 1, width)
        if 0 < a < rows and 0 < b < rows:
            folded.add((min(a, rows-a), min(b, rows-b)))
        states ^= bit
    return folded


def audit(line):
    fields = line.split()
    n, gates = map(int, fields[1:3])
    target = int(fields[3], 16)
    bound, j, k, open_pin = map(int, fields[4:8])
    literals = [int(item) for item in fields[8:]]
    assert len({lit >> 1 for lit in literals}) == len(literals), "repeated variable"
    assert literals[0] & 1
    table = variable_map(n, gates)
    victim = table[literals[0] >> 1]
    rows, out = 1 << n, n + gates - 1
    assert 2 <= n <= 4 and 0 <= k < j < out
    dom = [set(range(1, rows//2 + 1)) for _ in range(out)]
    zero, one = [1]*out, [0]*out
    for obj in range(n):
        dom[obj] = {rows // 2}
        one[obj] = sum(((r >> obj) & 1) << r for r in range(rows))
        zero[obj] = ((1 << rows) - 1) ^ one[obj]
    ops = set(OPS)
    selected = {}
    for lit in literals[1:]:
        value = lit & 1  # value that makes the premise's clause literal false
        kind, *args = table[lit >> 1]
        if kind == "sel":
            pin, pred = args
            assert value and pin not in selected
            selected[pin] = pred
        elif kind == "count":
            obj, count = args
            assert not value
            dom[obj].remove(count)
        elif kind == "op":
            ops = {op for op in ops if ((op >> (1 + args[0])) & 1) == value}
        else:
            obj, row = args
            assert kind == "row" and obj in (j, k)
            (one if value else zero)[obj] |= 1 << row
    if open_pin == -1:
        assert victim[0] == "count" and victim[1] in (j, k)
        dom[victim[1]].intersection_update([victim[2]])
    else:
        assert open_pin in (0, 1) and open_pin not in selected
        assert victim == ("sel", open_pin, (j, k)[open_pin])
        selected[open_pin] = victim[2]
    assert selected == {0: j, 1: k}
    cost = lambda a: 2*a*(rows-a)
    base = sum(cost(min(dom[g])) for g in range(n, out) if g not in (j, k))
    for op in ops:
        for a, b in possible(rows, target, op, zero[j], one[j], zero[k], one[k]):
            if a in dom[j] and b in dom[k]:
                assert base + (cost(a) if j >= n else 0) + (cost(b) if k >= n else 0) > bound, (
                    "satisfiable reason", op, a, b, line)
    return victim[0]


def summarize(log):
    counts = Counter()
    printed = Counter()
    examples = {}
    for line in log.read_text(errors="strict").splitlines():
        if line.startswith("REASON "):
            kind = audit(line)
            counts[kind] += 1
            examples.setdefault(kind, line)
        if line.startswith("JOINT "):
            stats = dict(item.split("=") for item in line.split()[1:])
            printed["count"] += int(stats["counts"])
            printed["sel"] += int(stats["edges"])
    assert counts == printed, (counts, printed)
    return dict(log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
                verified=dict(counts), examples=examples)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    results = {str(p.parent.name): summarize(p) for p in args.logs}
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({key: val["verified"] for key, val in results.items()}))
