"""Acquire an idle physical core per full mirrored block, quarantine collisions and resume."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime,timezone
import hashlib
import argparse
from host import physical_mask,conflicts
from run import HERE,ROOT,DEV,TEST,dump
from audit_results import examine,diagnostic_summary,timing_summary

def idle():
    cpus={}
    for cpu in range(os.cpu_count()):
        cpus.setdefault(physical_mask(cpu),cpu)
    # Avoid treating a gap between separately launched workers as sustained idle time.
    streak=dict.fromkeys(cpus,0)
    while True:
        for mask,cpu in cpus.items():
            streak[mask]=0 if conflicts(mask,0) else streak[mask]+1
            if streak[mask]>=4: return cpu,mask
        time.sleep(4)

def series(ref,part,kind,raw):
    diag=kind=='audit'
    cases=DEV if part=='dev' else TEST
    result={}
    for t in cases:
        n=0
        while True:
            n+=1
            label=f'core-{t}-{n}'
            path=raw/f'{part}-{kind}-{label}'
            if path.exists():
                if (path/'host.json').exists():
                    h=json.loads((path/'host.json').read_bytes())
                    if h['returncode']==0 and not h['clashes']: break
                continue
            cpu,mask=idle()
            path.mkdir(parents=True,exist_ok=False)
            binaries=dict(A=ref/'.local/variants/joint/abc.exe',B=ref/'.local/variants/screen-guide/abc.exe',
                          C=HERE/'.local/conditional/abc.exe',audit=HERE/'.local/audit/abc.exe')
            dump(path/'freeze.json',dict(cpu=cpu,physical_mask=mask,revision=subprocess.check_output(
                ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),hashes={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in binaries.items()},
                start_utc=datetime.now(timezone.utc).isoformat()))
            cmd=[sys.executable,str(HERE/'run.py'),str(ref),part,'--worker','--only',t,'--cpu',str(cpu),'--batch',label,'--raw-dir',str(raw)]
            if diag: cmd.append('--diag')
            clashes=[]
            scans=0
            with subprocess.Popen(cmd) as child:
                while child.poll() is None:
                    scans+=1
                    found=conflicts(mask,child.pid)
                    if found:
                        clashes.append([time.time(),found])
                        # Only the newly created process and its own solver child.
                        if child.poll() is None:
                            subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True)
                        break
                    time.sleep(.10)
                code=child.wait()
            dump(path/'host.json',dict(returncode=code,worker_pid=child.pid,clashes=clashes,scans=scans))
            if clashes: continue
            if code: raise RuntimeError(path)
            break
        result.update(examine(path,[t],diag,full_order=cases))
        print(part,kind,t,'accepted',flush=True)
    summary=diagnostic_summary(result) if diag else timing_summary(result)
    dump(raw/f'{part}-{kind}-summary.json',summary)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('ref',type=Path)
    p.add_argument('--raw-dir',type=Path,default=HERE/'raw')
    args=p.parse_args()
    ref=args.ref.resolve()
    for part in ('dev','holdout'):
        series(ref,part,'audit',args.raw_dir.resolve())
        series(ref,part,'timed',args.raw_dir.resolve())
