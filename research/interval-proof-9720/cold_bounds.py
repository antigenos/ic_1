"""Prove one four-input optimum up to a declared bound, starting with primary inputs only."""
import argparse
import json
import time

from construct_bounds import construct
from family import pin
from family_bounds import enumerate_bounds


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("truth", help="Full-support four-input truth table in hexadecimal")
    cli.add_argument("--cap", type=int, required=True, help="Exclusive activity bound")
    cli.add_argument("--cpu", type=int, required=True)
    args = cli.parse_args()
    target = int(args.truth, 16)
    if not 0 <= target <= 65535 or not all(
        any(((target >> row) ^ (target >> (row ^ (1 << k)))) & 1 for row in range(16))
        for k in range(4)
    ):
        cli.error("Expected a four-input function depending on all four inputs")
    truth = f"{target:04x}"
    pin(args.cpu)
    started = time.process_time()
    states = {}
    proof = enumerate_bounds([truth], args.cap, states)
    lower = proof["lower_bounds"][truth]
    result = dict(truth=truth, strict_cap=args.cap, states=proof["states"], lower_bound=lower,
                  logical_cpu=args.cpu, status="no_solution_below_cap")
    if truth in states:
        result.update(construct(truth, states[truth], lower))
        result["status"] = "independently_optimal"
    result["cpu_s"] = time.process_time() - started
    print(json.dumps(result))


if __name__ == "__main__":
    main()
