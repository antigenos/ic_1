"""Decode the native first-gate clauses independently using Python orbit enumeration."""
from collections import defaultdict
import argparse
import json
from pathlib import Path
from check_symmetry import FIRST, PINS, gate, leaders


def audit(path):
    seen = defaultdict(set)
    count = 0
    for line in path.read_text().splitlines():
        if not line.startswith("FIRST "):
            continue
        row = dict(token.split("=") for token in line.split()[1:])
        n, tt = int(row["nodes"]), int(row["target"],16)
        a,b,*bits = [int(v) for v in row["lits"].split(",")]
        assert a%2==b%2==1
        hi, lo = (a>>1)-(1+3*n), (b>>1)-(1+3*n+4)
        assert 4>hi>lo>=0
        assert [v>>1 for v in bits]==[1,2,3]
        op = sum((v&1)<<k for k,v in enumerate(bits,1))
        truth = gate(op,PINS[lo],PINS[hi])
        assert truth==int(row["h"],16) and truth not in leaders(tt,True)
        seen[tt].add(truth)
        count += 1
    assert count and all(v==FIRST-leaders(tt,True) for tt,v in seen.items())
    return dict(decoded=count,distinct_exclusions={f"{t:04x}":len(v) for t,v in seen.items()})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("log",type=Path)
    print(json.dumps(audit(p.parse_args().log),indent=2))
