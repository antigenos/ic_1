"""Validate the 14 excluded representatives on their actual input support."""
import argparse
import json
import os
from pathlib import Path

from compare import BINS, VERIFIED, dump
from function_family import family
from lower_bound import cheaper_circuit
from repeat_0189 import pin
from run_case import run


def project(truth, inputs):
    reduced = 0
    for r in range(1 << len(inputs)):
        src = sum(((r >> k) & 1) << v for k, v in enumerate(inputs))
        reduced |= ((truth >> src) & 1) << r
    lifted = 0
    for r in range(16):
        idx = sum(((r >> v) & 1) << k for k, v in enumerate(inputs))
        lifted |= ((reduced >> idx) & 1) << r
    assert lifted == truth
    return reduced


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu", type=int, default=0)
    args = parser.parse_args()
    pin(args.cpu)
    args.dest.mkdir(parents=True, exist_ok=False)
    records = []
    for item in family()["boundary"]:
        truth, inputs = int(item["truth"], 16), item["essential_inputs"]
        reduced = project(truth, inputs)
        n = len(inputs)
        mask = (1 << (1 << n)) - 1
        assert (project(truth ^ 65535, inputs) ^ reduced) == mask
        phase = reduced & 1
        normal = reduced ^ (mask if phase else 0)
        record = dict(**item, reduced=hex(reduced), normalized=hex(normal), output_phase=phase)
        if n < 3:
            allowed = {0: {0}, 1: {2}, 2: {2, 4, 6, 8, 14}}
            assert normal in allowed[n]
            record.update(construction=["constant", "literal", "single output gate"][n])
            optimum = 0
        else:
            text = f"{reduced:02x}"
            observations = {}
            env = {k: v for k, v in os.environ.items() if not k.startswith("REPLAY_")}
            for role in ("author", "joint"):
                dest = args.dest / item["truth"] / role
                result = run(BINS[role], text, n, 2, 60, dest, env=env,
                             metadata={"cpu": args.cpu, "group": "boundary", "method": role})
                if result["status"] != VERIFIED:
                    raise RuntimeError(f"Invalid boundary solution: {dest}")
                observations[role] = dict(witness=result["witness"],
                                          solver_output=(dest / "solver.log").read_text())
            optimum = observations["author"]["witness"]["activity"]
            assert observations["joint"]["witness"]["activity"] == optimum
            cheaper, states = cheaper_circuit(n, reduced, optimum)
            assert not cheaper, (item, optimum)
            record.update(reduced_runs=observations, strict_bound_states=states)
        record.update(reduced_optimum=optimum, lifted_witness_activity=optimum * (1 << (4-n))**2)
        records.append(record)
        dump(args.output, records)
    print(json.dumps({"passed": len(records), "three_input_comparisons":
                      sum("reduced_runs" in row for row in records)}))


if __name__ == "__main__":
    main()
