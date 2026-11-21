"""Run one ordered, CPU-pinned comparison and export every completed trial."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]/"tools"))
from repeat_0189 import pin
from run_case import run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frozen",type=Path)
    ap.add_argument("truth")
    ap.add_argument("order",help="A frozen, B both, C saved witness, D domain-only, H history-only, O off")
    ap.add_argument("tag")
    ap.add_argument("--cpu",type=int,required=True)
    ap.add_argument("--cap",type=int,required=True)
    args = ap.parse_args()
    pin(args.cpu)
    ext = ".exe" if os.name=="nt" else ""
    candidate = HERE/".local/build"/("abc"+ext)
    dest = HERE/".local/runs"/args.tag
    dest.mkdir(parents=True,exist_ok=False)
    export = HERE/"evidence"/(args.tag+".jsonl")
    modes = dict(A="frozen",B="both",C="both",D="domain",H="history",O="off")
    with export.open("x",encoding="utf-8") as out:
        for i,arm in enumerate(args.order,1):
            binary = args.frozen.resolve()/".local/variants/joint"/("abc"+ext) if arm=="A" else candidate
            if arm=="C":
                binary = HERE/".local/build-saved"/("abc"+ext)
            env = {k:v for k,v in os.environ.items() if not k.startswith(("REPLAY_","OPTWIN_"))}
            if arm!="A":
                env["OPTWIN_MODE"] = modes[arm]
            trial = dest/f"{i}-{arm}"
            meta = dict(truth=args.truth, order=i, arm=arm, mode=modes[arm],cpu=args.cpu)
            row = run(binary,args.truth,4,2,args.cap,trial,env=env,metadata=meta)
            raw = (trial/"solver.log").read_bytes()
            row.update(solver_output=raw.decode(),solver_log_sha256=hashlib.sha256(raw).hexdigest())
            out.write(json.dumps(row,separators=(",",":"))+"\n")
            out.flush()
            print(arm,row["status"],round(row["wall_s"],3),flush=True)
            if row["status"]=="unverified" or row["wall_s"]>args.cap+3:
                raise RuntimeError("Invalid trial; inspect its output")


if __name__ == "__main__":
    main()
