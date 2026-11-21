"""Run registered paired end-to-end tests and replay each emitted circuit."""
import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from repeat_0189 import pin
from run_case import run


def run_group(truth, cpu, order, cap, dest):
    pin(cpu)
    dest.mkdir(parents=True,exist_ok=False)
    activities = set()
    suffix = ".exe" if os.name == "nt" else ""
    for i,arm in enumerate(order,1):
        env = {k:v for k,v in os.environ.items() if not k.startswith(("PEXACT_ORBIT","REPLAY_"))}
        variant = {"A":"orbit-control","B":"orbit-signed","P":"orbit-signed",
                   "X":"orbit-signed","S":"orbit-order-control"}[arm]
        env["PEXACT_ORBIT"] = {"A":"off","B":"signed","P":"perm","X":"off","S":"off"}[arm]
        binary = ROOT / ".local/variants" / variant / ("abc"+suffix)
        r = run(binary,truth,4,2,cap,dest/f"{i}-{arm}",env=env,
                metadata=dict(cpu=cpu,truth=truth,arm=arm,order=i))
        if r["status"]=="unverified" or r["wall_s"]>cap+3:
            raise ValueError((truth,arm,r))
        if "witness" in r:
            activities.add(r["witness"]["activity"])
            assert len(activities)==1
        print(truth,arm,round(r["wall_s"],3),r["status"],flush=True)


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("truth")
    p.add_argument("dest",type=Path)
    p.add_argument("--cpu",type=int,required=True)
    p.add_argument("--order",default="ABBAPX")
    p.add_argument("--cap",type=int,default=30)
    a=p.parse_args()
    run_group(a.truth,a.cpu,a.order,a.cap,a.dest)
