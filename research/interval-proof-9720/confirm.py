"""Select an independent stratified panel from frozen TCJAP timings, then run it."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
PLAN = HERE / "evidence/confirmation-plan.json"


def plan():
    with ZipFile(HERE/"final-reproduction.zip") as z:
        rows = [json.loads(s) for s in z.read("evidence/e14-main/both.jsonl").splitlines()]
    strata = [[] for _ in range(4)]
    for row in rows:
        t = row["experiment"]["truth"]
        if t in {"0189","018b","001e"}:
            continue
        s = 3 if row["status"]=="timeout" else 2 if row["wall_s"]>=15 else 1 if row["wall_s"]>=2 else 0
        strata[s].append(t)
    entries = []
    for s, items in enumerate(strata):
        selected = sorted(items,key=lambda t:hashlib.sha256(("interval-9720-v1/"+t).encode()).digest())[:3]
        for j,t in enumerate(selected):
            entries.append(dict(truth=t,stratum=s,cpu=(16,20,24)[j],order="CA" if (s+j)%2 else "AC"))
    return dict(cap=30,selection="first three by sha256(interval-9720-v1/ + four-digit truth) within stratum",
                strata=["frozen <2s","2s to <15s","15s to completion","timeout at 300s"],cases=entries)


def lane(cpu,cases,frozen,cap,run_id):
    for item in cases:
        if item["cpu"]!=cpu:
            continue
        t,order = item["truth"],item["order"]
        tag = "confirmation-"+t+("-"+run_id if run_id else "")
        existing = HERE/"evidence"/(tag+".jsonl")
        if existing.exists():
            saved = [json.loads(s) for s in existing.read_text().splitlines()]
            if "".join(r["experiment"]["arm"] for r in saved)!=order:
                raise RuntimeError("Review the incomplete run before resuming: "+t)
            if not all(r["experiment"]["truth"]==t and r["experiment"]["cpu"]==cpu
                       and r["timeout_s"]==cap and r["status"] in {"timeout","solver_completed_verified_witness"}
                       and r["wall_s"]<=cap+3 for r in saved):
                raise RuntimeError("Review the completed run: "+t)
            continue
        subprocess.run([sys.executable,str(HERE/"paired.py"),str(frozen),t,order,tag,
                        "--cpu",str(cpu),"--cap",str(cap)],check=True)


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("frozen",type=Path)
    ap.add_argument("--plan",action="store_true")
    ap.add_argument("--run-id",default="",help="Use a new label to repeat the complete published panel")
    args=ap.parse_args()
    if args.run_id and not re.fullmatch(r"[A-Za-z0-9-]+",args.run_id):
        ap.error("--run-id must use letters, digits or hyphens")
    study=plan()
    if args.plan:
        with PLAN.open("x") as out:
            json.dump(study,out,indent=2)
            out.write("\n")
    else:
        assert json.loads(PLAN.read_text())==study
        with ThreadPoolExecutor(max_workers=3) as workers:
            futures=[workers.submit(lane,cpu,study["cases"],args.frozen.resolve(),study["cap"],args.run_id)
                     for cpu in sorted({r["cpu"] for r in study["cases"]})]
            for future in futures:
                future.result()
