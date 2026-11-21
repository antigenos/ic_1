"""Execute a predeclared sequence of complete optimizations on one logical CPU."""
import argparse
import json
import os
from pathlib import Path
from repeat_0189 import pin
from run_case import run

ROOT = Path(__file__).resolve().parents[1]
BINARIES = {"A": "joint", "B": "cofactor", "C": "sharedcone", "D": "sharedcone"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dest", type=Path)
    p.add_argument("truth")
    p.add_argument("order", help="A baseline, B primary-only, C both, D axes-only shared cuts")
    p.add_argument("--cap", type=int, default=300)
    p.add_argument("--cpu", type=int, default=2)
    args = p.parse_args()
    pin(args.cpu)
    args.dest.mkdir(parents=True, exist_ok=False)
    for idx, method in enumerate(args.order, 1):
        binary = ROOT / ".local/variants" / BINARIES[method] / ("abc.exe" if os.name == "nt" else "abc")
        env = {k: v for k, v in os.environ.items() if not k.startswith("REPLAY_")}
        if method == "D":
            env["REPLAY_SIDE"] = "axes"
        result = run(binary, args.truth, 4, 2, args.cap, args.dest / f"{idx}-{method}",
                     env=env, metadata=dict(cpu=args.cpu, truth=args.truth, arm=method, order=idx))
        print(json.dumps(dict(arm=method, status=result["status"], wall_s=result["wall_s"])), flush=True)
        if result["status"] == "unverified" or result["wall_s"] > args.cap + 3:
            raise RuntimeError("Invalid evidence requires review before continuing")


if __name__ == "__main__":
    main()
