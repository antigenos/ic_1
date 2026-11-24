"""Run registered complete-function triplets with preserved raw outputs."""
import argparse
from pathlib import Path
import os
import json
import hashlib
import subprocess
import time
import sys
from host import physical_mask, conflicts

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from repeat_0189 import pin
from run_case import run

DEV = ['0189','0019','0696']
TEST = ['0007','07f8','01ab','1be4','01ef','03dc']
def dump(path,obj):
    path.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')

def worker(args,binaries,batch):
    pin(args.cpu)
    env = {k:v for k,v in os.environ.items() if not k.startswith(('REPLAY_','GUIDE_'))}
    for i,t in enumerate(DEV if args.part=='dev' else TEST):
        if args.only and t != args.only: continue
        order = 'ABC'[i%3:] + 'ABC'[:i%3]
        arms = order if args.diag else order + order[::-1]
        for j,m in enumerate(arms):
            out = batch/t/f'{j+1}-{m}'
            if args.diag: env['GUIDE_AUDIT_ARM'] = m
            info = dict(truth=t,arm=m,order=j+1,cpu=args.cpu)
            row = run(binaries['audit' if args.diag else m],t,4,2,90 if args.diag else 30,out,env=env,metadata=info)
            if row['status'] not in ('solver_completed_verified_witness','timeout'):
                raise ValueError(row)
            if args.diag and row['status']=='solver_completed_verified_witness':
                lines = (out/'solver.log').read_text().splitlines()
                qs = [dict((k,int(v)) for k,v in (s.split('=') for s in l.split()[1:])) for l in lines if l.startswith('QUERY ')]
                if not qs or any(q['result'] not in (1,-1) for q in qs):
                    raise ValueError('Missing or unknown SAT queries')
                dump(out/'queries.json',qs)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('ref',type=Path)
    p.add_argument('part',choices=['dev','holdout'])
    p.add_argument('--diag',action='store_true')
    p.add_argument('--cpu',type=int,default=12)
    p.add_argument('--batch',default='1')
    p.add_argument('--worker',action='store_true')
    p.add_argument('--only',choices=DEV+TEST)
    args = p.parse_args()
    base = args.ref.resolve()/'.local/variants'
    bins = dict(A=base/'joint/abc.exe',B=base/'screen-guide/abc.exe',
                C=HERE/'.local/conditional/abc.exe',audit=HERE/'.local/audit/abc.exe')
    batch = HERE/'raw'/f'{args.part}-{"audit" if args.diag else "timed"}-{args.batch}'
    if args.worker:
        worker(args,bins,batch)
    else:
        mask = physical_mask(args.cpu)
        clean = 0
        while clean < 3:
            clean = 0 if conflicts(mask,0) else clean + 1
            if clean < 3: time.sleep(5)
        batch.mkdir(parents=True,exist_ok=False)
        plan=dict(cpu=args.cpu,physical_mask=mask,revision=subprocess.check_output(
            ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),hashes={
                k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in bins.items()})
        dump(batch/'freeze.json',plan)
        with subprocess.Popen([sys.executable,*sys.argv,'--worker']) as child:
            clashes = []
            scans = 0
            while child.poll() is None:
                found = conflicts(mask,child.pid)
                scans += 1
                if found: clashes.append([time.time(),found])
                time.sleep(0.1)
            dump(batch/'host.json',dict(scans=scans,clashes=clashes,worker_pid=child.pid,returncode=child.returncode))
            if child.returncode or clashes: raise SystemExit(1)
