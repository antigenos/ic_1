"""Compare terminal pruning with the full enumeration and its frozen lower bounds."""
import argparse
import json
from pathlib import Path
import random

from construct_bounds import available_gates, construct
from family import HERE, pin
from family_bounds import can_finish, enumerate_bounds


def check():
    frozen = json.loads((HERE / "evidence/family-bounds-432.json").read_bytes())["lower_bounds"]
    rng = random.Random(9720)
    for i in range(4000):
        signals = {rng.randrange(32768)*2 for _ in range(rng.randrange(1, 9))}
        x = rng.randrange(32768)*2
        while x in signals:
            x = rng.randrange(32768)*2
        outputs = {v for v, _, a, b in available_gates([x, *signals]) if x in (a, b)}
        target = rng.randrange(32768)*2 if i % 2 == 0 else min(outputs)
        assert can_finish(target, x, signals) == (target in outputs)
    checks = solved = 0
    for cap in (152, 153, 193, 225, 305):
        batch = list(frozen) if cap in (153, 225) else ["0001", "0006", "001e", "0189"]
        ref = enumerate_bounds(batch, cap)
        nonterminal = sum(n for cost, n in ref["states_by_cost"].items() if cost == 0 or cost+30 < cap)
        for truth in batch:
            states = {}
            found = enumerate_bounds([truth], cap, states, terminal=True)
            cost = found["lower_bounds"][truth]
            assert cost == min(frozen[truth], cap) == ref["lower_bounds"][truth]
            assert found["states"] == nonterminal
            if cost < cap:
                assert construct(truth, states[truth], cost)["witness"]["activity"] == cost
                solved += 1
            else:
                assert truth not in states
            checks += 1
    return dict(single_target_bounds=checks, legal_positives=solved, strict_negative=checks-solved,
                output_relation_tests=4000, seed=9720)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    pin(args.cpu)
    result = check()
    if args.output:
        with args.output.open("x", encoding="utf8", newline="\n") as output:
            json.dump(result, output, indent=2)
            output.write("\n")
    print(json.dumps(result))
