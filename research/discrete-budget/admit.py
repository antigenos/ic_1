"""Wait for a physical core free of competing timing lanes, then run a single panel."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from build import HERE
from guard import cores,competitors
from panel import D,V


def run(kind,label,preferred):
    log=HERE/"results"/(label+"-admission.jsonl")
    log.parent.mkdir(parents=True,exist_ok=True)
    if log.exists():
        raise ValueError("Use a fresh label; inspect earlier runs before relaunch")
    cpus=[g for g in cores() if preferred is None or preferred in g]
    if not cpus:
        raise ValueError("Invalid physical core")
    seen={}
    attempt=0
    pending=list(V if kind in ("holdout","confirm-audit") else D)
    with log.open("x",buffering=1) as f:
        while True:
            free=[]
            for group in cpus:
                k=group[0]
                if competitors(sum(1<<v for v in group),os.getpid()):
                    seen[k]=0
                else:
                    seen[k]=seen.get(k,0)+1
                    free.append(k)
            eligible=[k for k in free if seen[k]>=4]
            f.write(json.dumps(dict(t=datetime.now(timezone.utc).isoformat(),free=free))+"\n")
            if eligible:
                cpu=max(eligible)
                attempt+=1
                tag=label+"-"+pending[0]+"-a"+str(attempt)
                dest=HERE/"results"/tag
                print("Starting",tag,"on",cpu,flush=True)
                proc=subprocess.run([sys.executable,str(HERE/"panel.py"),kind,tag,"--cpu",str(cpu),"--truth",pending[0]],
                                     stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf8",errors="replace")
                (dest/"controller.log").write_text(proc.stdout,encoding="utf8")
                print(proc.stdout,flush=True)
                if proc.returncode==0:
                    pending.pop(0)
                    if not pending:
                        return
                elif not any(k in proc.stdout for k in ("Physical lane busy","foreign lane","competing timer")):
                    raise RuntimeError("Review error in "+str(dest))
                seen.clear()
            time.sleep(3)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("kind")
    p.add_argument("label")
    p.add_argument("--cpu",type=int)
    a=p.parse_args()
    run(a.kind,a.label,a.cpu)
