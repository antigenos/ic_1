"""Paired complete-solver screening with fixed CPU affinity and archived witnesses."""
import argparse
import json
import os
from pathlib import Path

from repeat_0189 import pin
from run_case import run

ROOT = Path(__file__).resolve().parents[1]
BINS = {"baseline":"joint", "cone":"cofactor", "shared":"sharedcone"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dest", type=Path)
    p.add_argument("truth")
    p.add_argument("--cpu", type=int, required=True)
    p.add_argument("order", nargs="+")
    args = p.parse_args()
    pin(args.cpu)
    reference = next(json.loads(s) for s in (ROOT/"evidence/e14-main/both.jsonl").read_text().splitlines()
                     if json.loads(s)["experiment"]["truth"] == args.truth)
    expected = reference["witness"]["activity"]
    args.dest.mkdir(parents=True, exist_ok=False)
    env = {k:v for k,v in os.environ.items() if not k.startswith("REPLAY_")}
    rows = []
    order = args.order + list(reversed(args.order))
    for i, name in enumerate(order, 1):
        binary = ROOT/".local/variants"/BINS.get(name,"screen-"+name)/("abc.exe" if os.name=="nt" else "abc")
        row = run(binary, args.truth, 4, 2, 30, args.dest/f"{i:02d}-{name}", env=env,
                  metadata=dict(method=name, truth=args.truth, cpu=args.cpu, order=i))
        rows.append({k:v for k,v in row.items() if k not in ("command","pid","returncode")})
        (args.dest/"paired.json").write_text(json.dumps(rows,indent=2)+"\n")
        if row["wall_s"] > 33 or (row["status"] != "timeout" and row.get("witness",{}).get("activity") != expected):
            raise ValueError((name, row["status"], row["wall_s"]))


if __name__ == "__main__":
    main()
