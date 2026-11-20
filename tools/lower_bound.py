"""Exhaustively test for a cheaper circuit, independently of the author's SAT encoding."""
import argparse
import itertools
import json
import time
from pathlib import Path


def cheaper_circuit(n, given, upper):
    rows = 1 << n
    mask = (1 << rows) - 1
    target = given ^ (mask if given & 1 else 0)
    primary = tuple(sum(((r >> k) & 1) << r for r in range(rows)) for k in range(n))
    if upper <= 0:
        return False, 0
    if target in (*primary, 0):
        return True, 0
    # A state contains distinct charged internal truth vectors. Cost depends only
    # on this set. Omitting repeated vectors loses no cheaper circuit: an earlier
    # copy can drive every later fanout. A zero vector is available for free,
    # which relaxes the library when proving infeasibility.
    stack = [((), 0)]
    seen = {()}
    while stack:
        state, cost = stack.pop()
        available = (0, *primary, *state)
        new_signals = set()
        for x, y in itertools.combinations(available, 2):
            outcomes = (x & ~y, y & ~x, x ^ y, x & y, x | y)
            if target in outcomes:
                return True, len(seen)
            new_signals.update(outcomes)
        new_signals.difference_update(available)
        for signal in new_signals:
            a = signal.bit_count()
            new_cost = cost + 2 * a * (rows - a)
            if new_cost >= upper:
                continue
            following = tuple(sorted((*state, signal)))
            if following not in seen:
                seen.add(following)
                stack.append((following, new_cost))
    return False, len(seen)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("witness_result", type=Path)
    args = p.parse_args()
    result = json.loads(args.witness_result.read_text())
    if result["status"] != "solver_completed_verified_witness":
        raise ValueError("A verified feasible witness supplies the upper bound")
    truth = result["witness"]["truth"]
    n = (4 * len(truth)).bit_length() - 1
    upper = result["witness"]["activity"]
    t = time.perf_counter()
    cheaper, states = cheaper_circuit(n, int(truth, 16), upper)
    print(json.dumps(dict(truth=truth, rows=1 << n, strict_upper=upper, states=states,
                          cheaper_exists=cheaper, seconds=time.perf_counter()-t)))
