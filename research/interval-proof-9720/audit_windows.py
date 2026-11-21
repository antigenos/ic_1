"""Replay each skipped window from prior UNSAT events and independently generated scores."""
import argparse
from collections import Counter, defaultdict
from functools import cache
import json
from pathlib import Path
import re


@cache
def scores(n, r):
    if r == 0:
        return {0}
    rows = 1 << n
    step = 1 << max(0, n - r - 1)
    return {s + 2*a*(rows-a) for s in scores(n,r-1) for a in range(step, rows//2+1, step)}


def audit(path):
    txt = path.read_text()
    n = int(re.search(r"pexact -I (\d+)",txt)[1])
    disproved = defaultdict(set)
    tally, times = Counter(), Counter()
    for line in txt.splitlines():
        if not line.startswith("WINDOW "):
            continue
        row = dict(t.split("=") for t in line.split()[1:])
        r, lo, hi = [int(row[k]) for k in ("r","lo","hi")]
        possible = scores(n,r).intersection(range(lo,hi+1))
        remaining = possible - disproved[r]
        kind = "empty_domain" if not possible else "proved" if not remaining else "pending"
        # A skipped query may have both syntactically attainable and known impossible scores.
        if row["state"] == "skip":
            assert not remaining, line
        if row["state"] == "1":
            assert remaining, line
        if row["state"] == "-1":
            disproved[r].update(range(lo,hi+1))
        tally[kind] += 1
        tally["skipped"] += row["state"] == "skip"
        times[kind] += float(row["seconds"])
    assert tally["pending"] > 0
    return dict(windows=sum(tally[k] for k in ("empty_domain","proved","pending")),
                counts=tally, window_cpu_seconds=times)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("trace", type=Path)
    print(json.dumps(audit(p.parse_args().trace), indent=2))
