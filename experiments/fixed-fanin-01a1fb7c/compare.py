"""Paired, pinned, full CLI timings and witness audits for the registered cases."""
import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from repeat_0189 import pin
from run_case import run


def collect(truth, cpu, dest, arms, cap):
    pin(cpu)
    dest.mkdir(parents=True, exist_ok=False)
    seen_costs = set()
    records = []
    for n, mode in enumerate(arms, 1):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("FF_", "REPLAY_"))}
        env["FF_MODE"] = mode
        kind = "base" if mode == "base" else "candidate"
        binary = ROOT / ".local/variants" / ("fixed-fanin-" + kind) / ("abc.exe" if os.name == "nt" else "abc")
        result = run(binary, truth, 4, 2, cap, dest/f"{n:02}-{mode}", env=env,
                     metadata=dict(cpu=cpu, truth=truth, mode=mode, order=n))
        if result["status"] == "unverified" or result["wall_s"] > cap+3:
            raise ValueError(f"Invalid result at {dest} run {n}")
        if "witness" in result:
            seen_costs.add(result["witness"]["activity"])
        if len(seen_costs)>1:
            raise ValueError(f"Activity mismatch {seen_costs}")
        records.append(dict(mode=mode, wall_s=result["wall_s"], capped_s=result["capped_wall_s"],
                            status=result["status"], activity=result.get("witness",{}).get("activity")))
        (dest/"summary.json").write_text(json.dumps(records,indent=2)+"\n")
        print(truth, mode, result["status"], round(result["wall_s"],3), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("truth")
    p.add_argument("directory",type=Path)
    p.add_argument("--cpu",type=int,required=True)
    p.add_argument("--cap",type=int,default=60)
    p.add_argument("--arms",nargs="+",choices=("base","ops","margins","all","off"),
                   default=("base","ops","margins","all","all","margins","ops","base"))
    args = p.parse_args()
    collect(args.truth,args.cpu,args.directory,args.arms,args.cap)
