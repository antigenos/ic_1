"""Use original TCJAP per-query counters to attribute changes in search work."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from repeat_0189 import pin
from run_case import run


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("truth")
    parser.add_argument("--cpu",type=int,default=24)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    pin(args.cpu)
    binary=ROOT/".local/variants/signed-symmetry-confirmed-01a1fb7c"/("abc.exe" if os.name=="nt" else "abc")
    records=[]
    metrics=("visits","checks","counts","edges","conflicts")
    for mode in ("chain","chain-unsigned","chain-first"):
        dest=ROOT/".local"/HERE.name/args.output.stem/mode
        env={k:v for k,v in os.environ.items() if not k.startswith("REPLAY_")}
        env.update(REPLAY_STATS="1",REPLAY_FIRST_SYMMETRY=mode)
        r=run(binary,args.truth,4,2,300,dest,env=env,metadata=dict(truth=args.truth,cpu=args.cpu,mode=mode))
        if r["status"]!="solver_completed_verified_witness":
            raise RuntimeError(f"Incomplete profiling row: {dest}")
        rows=[]
        for line in (dest/"solver.log").read_text().splitlines():
            if line.startswith("JOINT "):
                rows.append({k:int(v) for k,v in re.findall(r"(\w+)=(\d+)",line)})
        assert rows and all(all(k in row for k in ("gates","bound",*metrics)) for row in rows)
        records.append(dict(mode=mode,witness=r["witness"],binary_sha256=r["binary_sha256"],
                            measured_sat_calls=len(rows),totals={k:sum(row[k] for row in rows) for k in metrics},
                            queries=rows))
    assert len({r["witness"]["activity"] for r in records})==1
    with args.output.open("x",encoding="utf-8") as out:
        json.dump(records,out,indent=2)
    print(json.dumps([(r["mode"],r["measured_sat_calls"],r["totals"]) for r in records]))


if __name__=="__main__":
    main()
