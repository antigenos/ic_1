"""Verify a bounded-search witness against an independent exhaustive strict lower bound."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
from lower_bound import cheaper_circuit
from repeat_0189 import pin
from audit_bounded import replay


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("binary", type=Path)
    p.add_argument("truth")
    p.add_argument("output", type=Path)
    p.add_argument("--cpu", required=True, type=int)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    pin(args.cpu)
    inp = f"{args.truth} 480 2000000 2\n"
    run = subprocess.run([str(args.binary.resolve())], input=inp, text=True, capture_output=True, check=True)
    raw = json.loads(run.stdout)
    assert raw["complete"] and raw["found"]
    replay(raw)
    start = time.perf_counter()
    cheaper, count = cheaper_circuit(4, int(args.truth, 16), raw["cost"])
    assert not cheaper
    args.output.write_text(json.dumps(dict(truth=args.truth, strict_upper=raw["cost"], cheaper_exists=cheaper,
        independent_states=count, seconds=time.perf_counter()-start, cpu=args.cpu, candidate_certificate=raw),
        indent=2) + "\n")
