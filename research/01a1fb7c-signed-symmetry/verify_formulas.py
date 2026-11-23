"""Check the tree-cost table by constructive witnesses and all Bellman inequalities."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from check_symmetry import HERE, PINS, gate, norm
from family import write_once
from formula_control import formulas, shared
from repeat_0189 import pin
from witness import simulate


def verify(cap):
    evidence = json.loads((HERE/f"formula-{cap}.json").read_bytes())
    values, parents, _ = formulas(cap)
    leaves = {0, *PINS}
    assert set(values) == leaves | set(parents) and not leaves.intersection(parents)
    assert all(values[x] == 0 for x in leaves)
    # Count transitions directly between ordered pairs of input rows for each popcount.
    weights = [sum((i < n) != (j < n) for i in range(16) for j in range(16)) for n in range(17)]
    paid = {x:v+(0 if x in leaves else weights[x.bit_count()]) for x,v in values.items()}
    for x,(a,b,op) in parents.items():
        assert gate(op, a, b) == x and op in (2,4,6,8,14)
        assert values[x] == paid[a]+paid[b]
        assert all(y in leaves or values[y] < values[x] for y in (a,b))
    # If a cheaper output were reachable, its top gate would violate one of these inequalities.
    cheap = sorted((v,x) for x,v in paid.items() if v <= cap)
    checked = 0
    for i,(a_cost,a) in enumerate(cheap):
        for j in range(i, len(cheap)):
            b_cost,b = cheap[j]
            total = a_cost+b_cost
            if total > cap:
                break
            both = a & b
            xor = a ^ b
            for result in (both, xor, both | xor, a ^ both, b ^ both):
                assert values[result] <= total
            checked += 1
    for key,row in evidence["cases"].items():
        t = int(key,16)
        assert values.get(norm(t)) == row["formula"]
        if row["formula"] is not None:
            assert not shared(row["circuit"])
            assert simulate(row["circuit"],4,t) == row["witness"]
            assert row["witness"]["activity"] == row["formula"]
    # One signed integer per normalized four-input truth table; -1 denotes a proved open upper interval.
    canonical = b"".join(values.get(x,-1).to_bytes(2,"little",signed=True) for x in range(0,65536,2))
    return dict(cap=cap, finite=len(values), constructed=len(parents), pairs_with_repetition=checked,
                gate_inequalities=5*checked, normalized_value_sha256=sha256(canonical).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu", required=True, type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    pin(args.cpu)
    reports = [verify(cap) for cap in (560,720)]
    if args.output:
        write_once(args.output, (json.dumps(reports,indent=2)+"\n").encode())
    print(json.dumps(reports))
