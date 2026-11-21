"""Decode actual ABC clauses and verify their budget implications via the Python oracle."""
import argparse
from functools import cache
import json
from pathlib import Path

from check_cofactor_cones import PINS
from check_shared_cones import lower


@cache
def selectors(n):
    var = 1 + 3*n
    result = {}
    for obj in range(4, 4 + n):
        for pin in range(2):
            for j in range(obj - pin):
                result[var] = obj, pin, j
                var += 1
    return result


def audit(path):
    records = set()
    count = 0
    for line in path.read_text().splitlines():
        if not line.startswith("SIDE "):
            continue
        row = dict(token.split("=") for token in line.split()[1:])
        target, n, bound = int(row["target"], 16), int(row["gates"]), int(row["bound"])
        clause = [int(x) for x in row["lits"].split(",")]
        assert len(clause) == 6 and all(x & 1 for x in clause[:3])
        out_pin, high_pin, low_pin = [selectors(n)[x >> 1] for x in clause[:3]]
        assert out_pin == (3 + n, 1, 4) and high_pin[:2] == (4, 0) and low_pin[:2] == (4, 1)
        high, low = high_pin[2], low_pin[2]
        assert 4 > high > low >= 0
        assert [x >> 1 for x in clause[3:]] == [1, 2, 3]
        op = sum((lit & 1) << k for k, lit in enumerate(clause[3:], 1))
        h = sum(((op >> ((PINS[high] >> r & 1) + 2*(PINS[low] >> r & 1))) & 1) << r
                for r in range(16))
        assert h == int(row["first"], 16)
        possible = {(target >> r & 1, h >> r & 1) for r in range(16)}
        assert len(possible) == 4
        lb = lower(h, h ^ target)
        assert lb == int(row["lower"]) and lb > bound
        records.add((h, bound, n))
        count += 1
    assert count
    return dict(source=path.name, decoded_clauses=count, distinct_branches=len(records), failures=0)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("log", type=Path)
    print(json.dumps(audit(p.parse_args().log), indent=2))
