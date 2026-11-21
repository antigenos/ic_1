"""Independently reconstruct outstanding cheaper scores in a saved-model trace."""
from collections import defaultdict
import json
from pathlib import Path
import re
import sys

from audit_windows import scores


def audit(path):
    text = path.read_text()
    n, hex_truth = re.search(r"pexact -I (\d+) -M 2 ([0-9a-fA-F]+)",text).groups()
    n,truth = int(n),int(hex_truth,16)
    rows = 2**n
    support = sum(any((truth>>x ^ truth>>(x ^ (1<<i))) & 1 for x in range(rows)) for i in range(n))
    excluded = defaultdict(set)
    bound = final = None
    sat_window = None
    strict = 0
    improvements = 0
    for line in text.splitlines():
        op = line.split(" ",1)[0]
        if op not in {"WINDOW","INCUMBENT","STRICT","CERTIFIED","UNFINISHED"}:
            continue
        entry = dict(pair.split("=") for pair in line.split()[1:])
        if op in {"WINDOW","STRICT"}:
            r,lo,hi = (int(entry[k]) for k in ("r","lo","hi"))
            possible = scores(n,r)
            unresolved = possible - excluded[r]
            state = entry.get("state",entry.get("status"))
            if op == "STRICT":
                pending = {s for s in unresolved if s < bound}
                assert pending and (lo,hi)==(min(pending),max(pending)), line
                strict += 1
            if state == "-1":
                excluded[r].update(range(lo,hi+1))
            elif state == "skip":
                assert not unresolved.intersection(range(lo,hi+1)), line
            elif state == "1":
                sat_window = r,lo,hi
                if op == "STRICT":
                    score = int(entry["score"])
                    assert lo<=score<=hi and score<bound and score in unresolved
                    bound = score
                    improvements += 1
        elif op == "INCUMBENT":
            bound = int(entry["score"])
            r,lo,hi = sat_window
            assert lo<=bound<=hi and bound in scores(n,r) - excluded[r]
            assert int(entry["support"])==support and support>=3
        elif op == "UNFINISHED":
            bound = None
        else:
            assert int(entry["score"])==bound
            # Check the entire host gate range, not just the gate counts printed by the candidate.
            for r in range(1,32-n):
                if r+2 < support:
                    continue
                assert not {s for s in scores(n,r)-excluded[r] if s<bound}, (line,r)
            final = bound
    witness = json.loads(path.with_name("result.json").read_text())["witness"]
    assert final==witness["activity"]
    return dict(truth=hex_truth,activity=final,strict_queries=strict,improved_incumbents=improvements,
                remaining_cheaper_scores=0)


if __name__=="__main__":
    print(json.dumps([audit(Path(p)) for p in sys.argv[1:]],indent=2))
