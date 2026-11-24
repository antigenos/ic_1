"""Matched cold calls through the author ABC entry point, one pinned CPU."""
import argparse
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from repeat_0189 import pin
from run_case import run

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('cap',type=int)
    p.add_argument('dest',type=Path)
    p.add_argument('truth',nargs='+')
    p.add_argument('--seconds',type=float,default=300)
    p.add_argument('--cpu',type=int,default=16)
    p.add_argument('--variant',default='orbit-frontier-fixed')
    p.add_argument('--verify',choices=['fixed','range'],default='range')
    p.add_argument('--modes',nargs='+',choices=['projected','uniform','off'],default=['projected','uniform'])
    args=p.parse_args()
    pin(args.cpu)
    exe=ROOT/'.local/variants'/args.variant/('abc.exe' if os.name=='nt' else 'abc')
    for idx,truth in enumerate(args.truth):
        modes=args.modes if not idx%2 else args.modes[::-1]
        for mode in modes:
            env=dict(os.environ)
            env.pop('PEXACT_FRONTIER_CAP',None)
            env.pop('PEXACT_FRONTIER_COMPLETE',None)
            env.update(PEXACT_FRONTIER_MODE=mode,PEXACT_FRONTIER_TRACE='1',PEXACT_FRONTIER_VERIFY=args.verify)
            if mode!='off':
                env['PEXACT_FRONTIER_CAP']=str(args.cap)
            record=run(exe,truth,4,2,args.seconds,args.dest/truth/mode,env=env,
                       metadata=dict(cpu=args.cpu,cap=args.cap,mode=mode))
            print(truth,mode,record['status'],record['wall_s'],record.get('witness'),flush=True)
            if record['status']=='unverified':
                raise RuntimeError(record)
