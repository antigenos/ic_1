"""Find a native saved proof which replaced its first feasible model."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile

from audit_certificate import audit
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"tools"))
from repeat_0189 import pin
from run_case import run


def check(dest,cpu):
    dest.mkdir(parents=True,exist_ok=False)
    pin(cpu)
    with ZipFile(HERE/"final-reproduction.zip") as z:
        data=[json.loads(s) for s in z.read("evidence/e14-main/both.jsonl").splitlines()]
    panel={c["truth"] for c in json.loads((HERE/"evidence/confirmation-plan.json").read_text())["cases"]}
    # Preselected cheap non-panel functions in ABC table order; no timing comparisons.
    choices=[r for r in data if r["wall_s"]<2 and r["experiment"]["truth"] not in panel|{"0189","018b","001e"}]
    env={k:v for k,v in os.environ.items() if not k.startswith(("REPLAY_","OPTWIN_"))}
    env["OPTWIN_TRACE"]="1"
    binary=HERE/".local/build-saved"/("abc.exe" if os.name=="nt" else "abc")
    cases=[]
    for ref in choices[:12]:
        t=ref["experiment"]["truth"]
        work=dest/t
        row=run(binary,t,4,2,15,work,env=env,metadata={"cpu":cpu,"truth":t})
        assert row["witness"]["activity"]==ref["witness"]["activity"]
        raw=(work/"solver.log").read_bytes()
        proof=audit(work/"solver.log")
        cases.append(dict(result=row,certificate=proof,solver_output=raw.decode(),
                          solver_log_sha256=hashlib.sha256(raw).hexdigest()))
        if proof["improved_incumbents"]:
            break
    return dict(limit=12,selection="first frozen sub-2s full-support cases in ABC order, excluding design and confirmation",
                runs=cases,real_improvement_exercised=any(c["certificate"]["improved_incumbents"] for c in cases))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("dest",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--cpu",type=int,default=12)
    args=p.parse_args()
    data=check(args.dest,args.cpu)
    args.output.write_text(json.dumps(data,indent=2)+"\n",encoding="utf8")
    print(len(data["runs"]),data["real_improvement_exercised"])
