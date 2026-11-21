"""Run the first registered paired cost experiment on one CPU."""
import argparse
import json
import os
from pathlib import Path

from repeat_0189 import pin
from run_case import run


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("baseline", type=Path)
    p.add_argument("candidate", type=Path)
    p.add_argument("dest", type=Path)
    p.add_argument("--cpu", default=2, type=int)
    args = p.parse_args()
    pin(args.cpu)
    args.dest.mkdir(parents=True, exist_ok=False)
    rows = []
    for truth, order, cap in (("0189", "ABBAX", 60), ("018b", "BA", 300)):
        for idx, arm in enumerate(order):
            env = dict(os.environ)
            for k in ("REPLAY_RULES", "REPLAY_CONE", "REPLAY_BUDGET", "REPLAY_STATS",
                      "REPLAY_CONE_TRACE", "REPLAY_TRACE"):
                env.pop(k, None)
            if arm == "X":
                env["REPLAY_CONE"] = "off"
            dest = args.dest / f"{truth}-{idx + 1}-{arm}"
            binary = args.baseline if arm == "A" else args.candidate
            result = run(binary, truth, 4, 2, cap, dest, env=env,
                         metadata=dict(cpu=args.cpu, arm=arm, truth=truth, order=idx+1))
            rows.append(result)
            (args.dest / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
            if result["status"] == "unverified" or (truth == "0189" and
                    result.get("witness", {}).get("activity") != 304):
                raise RuntimeError(f"Review {dest}")
