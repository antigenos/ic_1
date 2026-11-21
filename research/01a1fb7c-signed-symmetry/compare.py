"""Serial paired measurements on one pinned logical processor, with original logs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from summarize import replay

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
    p.add_argument("--raw-root",type=Path,default=ROOT/".local"/HERE.name)
    p.add_argument("--resume-id",help="A new alphanumeric identifier after verifying the former launcher has stopped")
    args = p.parse_args()
    modes = {"F":"off","O":"off","U":"unsigned","S":"signed","P":"first-use",
             "J":"combined","K":"ordered","R":"sorted-prefix","T":"orbit-prefix",
             "Q":"chain","H":"chain-unsigned","N":"chain-first","M":"chain-sorted","V":"chain-orbit",
             "A":"chain-first","D":"chain-first","B":"chain-first","C":"chain-first",
             "I":"chain-first","L":"chain-first","E":"chain-first","W":"chain-first","Y":"chain-first","Z":"chain-first",
             "0":"chain-first","1":"chain-first","2":"chain-first"}
    if set(args.order)-set(modes):
        p.error("Unknown method")
    pin(args.cpu)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.resume_id and not args.resume_id.isalnum():
        p.error("Use an alphanumeric resume identifier")
    raw = args.raw_root/args.output.stem
    old = []
    if args.resume_id and args.output.exists():
        n = len(args.output.read_text().splitlines())
        old = replay(args.output,args.target,args.order[:n],args.cpu,args.cap)
        if n == len(args.order):
            return
    if args.resume_id:
        raw = raw/("resume-" + args.resume_id)
    raw.mkdir(parents=True,exist_ok=False)
    checked_activity = next((r["witness"]["activity"] for r in old if "witness" in r),None)
    with args.output.open("a" if args.resume_id else "x",encoding="utf-8") as out:
        for i,key in enumerate(args.order,1):
            if i <= len(old):
                continue
            dest = raw/f"{i}-{key}"
            base = args.prepared.resolve()/".local/variants/joint" if key=="F" else ROOT/".local/variants/signed-symmetry-confirmed-01a1fb7c"
            if key in "ADBC":
                base = ROOT/".local/variants/restriction-01a1fb7c"
            if key in "ILE":
                base = ROOT/".local/variants/endpoint-01a1fb7c"
            if key in "WYZ":
                base = ROOT/".local/variants/endpoint-short-01a1fb7c"
            if key in "012":
                base = ROOT/".local/variants/closure-01a1fb7c"
            binary = base/("abc.exe" if os.name=="nt" else "abc")
            env = {k:v for k,v in os.environ.items() if not k.startswith("REPLAY_")}
            env["REPLAY_FIRST_SYMMETRY"] = modes[key]
            if key in "DBC":
                env["REPLAY_RESTRICTION"] = {"D":"global","B":"size","C":"cost"}[key]
            if key in "ILEWYZ":
                env["REPLAY_RESTRICTION"] = "size"
            if key in "LE":
                env["REPLAY_ENDPOINT"] = "joint" if key=="E" else "margins"
            if key in "WYZ":
                env["REPLAY_ENDPOINT"] = {"W":"margins","Y":"joint","Z":"short"}[key]
            if key in "12":
                env["REPLAY_COLD_CLOSURE"] = "lower" if key=="1" else "size"
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
