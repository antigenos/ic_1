"""Run one registered panel; all timing blocks are reversible, same physical lane per truth."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from build import HERE, ROOT, OUTER, gitfile
from guard import cores, competitors
sys.path.insert(0,str(ROOT/"tools"))
from repeat_0189 import pin
from run_case import run

D=("0189","0019")
V=("003d","001b","013e","0199")
THREE=["joint","interval","holes"]
FOUR=THREE+["trigger"]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def panel(kind,label,cpu):
    folder=HERE/"results"/label
    folder.mkdir(parents=True,exist_ok=False)
    diagnostic=kind in ("profile","trace","trigger-profile","trigger-trace")
    methods=(["trigger"] if kind.startswith("trigger-") else FOUR if kind in ("holdout","four") else THREE)
    truths=V if kind=="holdout" else D
    suffix="-profile" if kind.endswith("profile") else ""
    bounds=json.loads(gitfile("evidence/family-bounds-432.json"))["lower_bounds"]
    env={k:v for k,v in os.environ.items() if not k.startswith(("OPTWIN_","REPLAY_"))}
    env.update(OPTWIN_MODE="both",REPLAY_RULES="both",REPLAY_BUDGET="1")
    if diagnostic:
        env.update(OPTWIN_TRACE="1",REPLAY_STATS="1")
        if kind.endswith("trace"):
            env["REPLAY_TRACE"]="1"
    binaries={m:HERE/".local"/(m+suffix)/"abc.exe" for m in methods}
    commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    core=next(c for c in cores() if cpu in c)
    mask=sum(1<<v for v in core)
    manifest=dict(kind=kind,cases=truths,source_commit=commit,outer=OUTER,cpu=cpu,physical=core,
                  methods=methods,binaries={m:sha(p) for m,p in binaries.items()},cap=120 if diagnostic else 30,
                  env={k:v for k,v in env.items() if k.startswith(("OPTWIN_","REPLAY_"))},
                  reference={t:bounds[t] for t in truths},order="forward then reverse; alternate first direction across functions")
    (folder/"manifest.json").write_text(json.dumps(manifest,indent=2))
    competing=competitors(mask,os.getpid())
    if competing:
        raise RuntimeError(("Physical lane busy",core,competing))
    watcher=subprocess.Popen([sys.executable,str(HERE/"guard.py"),str(folder),str(cpu),str(os.getpid())],cwd=folder)
    try:
        pin(cpu)
        for i in range(100):
            if (folder/"guard.jsonl").exists() and (folder/"guard.jsonl").stat().st_size:
                break
            if watcher.poll() is not None:
                raise RuntimeError("Guard failed")
            time.sleep(.05)
        else:
            raise RuntimeError("Guard did not start")
        for n,t in enumerate(truths):
            order=methods[::-1] if n%2 else methods[:]
            order=order if diagnostic else order+order[::-1]
            for i,m in enumerate(order,1):
                if watcher.poll() is not None or competitors(mask,os.getpid()):
                    raise RuntimeError("Active foreign lane; preserve this attempt")
                dest=folder/(t+"-"+str(i)+"-"+m)
                r=run(binaries[m],t,4,2,manifest["cap"],dest,env=env,
                      metadata=dict(truth=t,method=m,cpu=cpu,order=i,diagnostic=diagnostic))
                if r["status"]!="timeout":
                    if r.get("witness",{}).get("activity")!=bounds[t] or r["status"]!="solver_completed_verified_witness":
                        raise ValueError(("Optimum/witness mismatch",dest,r))
                elif diagnostic:
                    raise RuntimeError(("Incomplete diagnostic",dest))
                if kind.endswith("trace"):
                    with (dest/"solver.log.gz").open("wb") as f:
                        f.write(gzip.compress((dest/"solver.log").read_bytes(),mtime=0))
                    (dest/"solver.log").unlink()  # Lossless gzip in the dedicated new run directory.
                print(t,m,i,r["status"],round(r["wall_s"],4),flush=True)
        time.sleep(.23)
    finally:
        (folder/"guard.stop").touch()
        watcher.wait(timeout=8)
    samples=[json.loads(s) for s in (folder/"guard.jsonl").read_text().splitlines()]
    if not samples or any(s["foreign"] for s in samples):
        raise RuntimeError("Observed competing timer; invalidate this panel")
    (folder/"complete.json").write_text(json.dumps(dict(samples=len(samples),max_sample_gap=max(
        (b["t"]-a["t"] for a,b in zip(samples,samples[1:])),default=0),observed_overlap=0)))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("kind",choices=("three","four","holdout","profile","trace","trigger-profile","trigger-trace"))
    p.add_argument("label")
    p.add_argument("--cpu",type=int,default=0)
    args=p.parse_args()
    panel(args.kind,args.label,args.cpu)
