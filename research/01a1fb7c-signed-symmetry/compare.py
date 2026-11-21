"""Serial paired measurements on one pinned logical processor, with original logs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from repeat_0189 import pin
from run_case import run


def main():
    p = argparse.ArgumentParser()
    p.add_argument("target")
    p.add_argument("order",help="F frozen; O/U/S/P/J/K/R/T pilot modes; Q/H/N/M/V chain comparisons")
    p.add_argument("output",type=Path)
    p.add_argument("--prepared",type=Path,default=ROOT)
    p.add_argument("--cap",type=int,default=300)
    p.add_argument("--cpu",type=int,default=14)
    args = p.parse_args()
    modes = {"F":"off","O":"off","U":"unsigned","S":"signed","P":"first-use",
             "J":"combined","K":"ordered","R":"sorted-prefix","T":"orbit-prefix",
             "Q":"chain","H":"chain-unsigned","N":"chain-first","M":"chain-sorted","V":"chain-orbit"}
    if set(args.order)-set(modes):
        p.error("Unknown method")
    pin(args.cpu)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    raw = ROOT/".local"/HERE.name/args.output.stem
    raw.mkdir(parents=True,exist_ok=False)
    checked_activity = None
    with args.output.open("x",encoding="utf-8") as out:
        for i,key in enumerate(args.order,1):
            dest = raw/f"{i}-{key}"
            base = args.prepared.resolve()/".local/variants/joint" if key=="F" else ROOT/".local/variants/signed-symmetry-confirmed-01a1fb7c"
            binary = base/("abc.exe" if os.name=="nt" else "abc")
            env = {k:v for k,v in os.environ.items() if not k.startswith("REPLAY_")}
            env["REPLAY_FIRST_SYMMETRY"] = modes[key]
            entry = run(binary,args.target,4,2,args.cap,dest,env=env,
                        metadata=dict(cpu=args.cpu,arm=key,order=i,truth=args.target))
            data = (dest/"solver.log").read_bytes()
            entry.update(solver_output=data.decode("utf-8", errors="replace"),
                         solver_log_sha256=hashlib.sha256(data).hexdigest())
            out.write(json.dumps(entry,ensure_ascii=True)+"\n")
            out.flush()
            print(key, entry["status"], round(entry["wall_s"],3), flush=True)
            if entry["wall_s"]>args.cap+3 or entry["status"]=="unverified":
                raise RuntimeError("Invalid timing or witness, inspect the preserved run")
            if "witness" in entry:
                score = entry["witness"]["activity"]
                if checked_activity is not None and checked_activity != score:
                    raise RuntimeError("Paired witnesses disagree")
                checked_activity = score


if __name__ == "__main__":
    main()
