"""Check complete reason sequences and every fixed-input call in a real search."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/"tools"))
from audit_trail import summarize
from repeat_0189 import pin
from run_case import run


def check(dest, output, cpu):
    pin(cpu)
    dest.mkdir(parents=True, exist_ok=False)
    env = {k:v for k,v in os.environ.items() if not k.startswith(("REPLAY_","FF_"))}
    env.update(REPLAY_TRACE="1", FF_STATS="1", FF_CROSSCHECK="1")
    comparison = {}
    for kind in ("base","interval"):
        binary=ROOT/".local/variants"/("fixed-fanin-"+kind)/("abc.exe" if os.name=="nt" else "abc")
        res=run(binary,"0189",4,2,60,dest/kind,env=env,metadata=dict(cpu=cpu,kind=kind))
        assert res.get("witness",{}).get("activity")==304
        log=dest/kind/"solver.log"
        lines=log.read_bytes().splitlines()
        reasons=[s for s in lines if s.startswith(b"REASON ")]
        joint=[s for s in lines if s.startswith(b"JOINT ")]
        assert reasons and joint
        observation=dict(reasons=len(reasons), queries=len(joint), binary_sha256=res["binary_sha256"],
                         reason_sha256=hashlib.sha256(b"\n".join(reasons)).hexdigest(),
                         statistics_sha256=hashlib.sha256(b"\n".join(joint)).hexdigest())
        if kind=="interval":
            calls=[tuple(map(int,s.split()[1:])) for s in lines if s.startswith(b"FF_CALLS ")]
            assert len(calls)==len(joint)
            observation.update(checked_fixed_calls=sum(a for a,_ in calls), total_calls=sum(b for _,b in calls))
            assert observation["checked_fixed_calls"]>0
            observation["independent_audit"]=summarize(log)["verified"]
        comparison[kind]=observation
    for name in ("reason_sha256","statistics_sha256","queries","reasons"):
        assert comparison["base"][name]==comparison["interval"][name], name
    output.write_text(json.dumps(comparison,indent=2)+"\n")
    return comparison


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("raw",type=Path)
    p.add_argument("summary",type=Path)
    p.add_argument("--cpu",type=int,required=True)
    args=p.parse_args()
    print(json.dumps(check(args.raw,args.summary,args.cpu),indent=2))
