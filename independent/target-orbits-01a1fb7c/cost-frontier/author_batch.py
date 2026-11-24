"""Run every published representative through one cold author process and recheck each SAT printout."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from audit import HERE, STUDY, simulate
from run import peak_bytes
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from repeat_0189 import pin
from run_case import child_cpus


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('audit',type=Path)
    p.add_argument('out',type=Path)
    p.add_argument('--cpu',type=int,default=18)
    args=p.parse_args()
    pin(args.cpu)
    args.out.mkdir(parents=True,exist_ok=False)
    exe=ROOT/'.local/variants/orbit-frontier-complete'/('abc.exe' if os.name=='nt' else 'abc')
    family=json.loads((STUDY/'reproduction/evidence/npn-family.json').read_text())['essential']
    reference={r['truth']:r for r in json.loads(args.audit.read_text())['targets']}
    assert len(family)==len(set(family))==len(reference)==208
    script=args.out/'batch.abc'
    script.write_text(''.join(f'echo CF_BEGIN_{t}\npexact -I 4 -M 2 {t}\necho CF_END_{t}\n' for t in family))
    env=dict(os.environ,PEXACT_FRONTIER_CAP='520',PEXACT_FRONTIER_MODE='projected',
             PEXACT_FRONTIER_COMPLETE='1',PEXACT_FRONTIER_TRACE='1')
    start=time.perf_counter()
    with (args.out/'solver.log').open('wb') as log:
        p=subprocess.Popen([str(exe),'-f',script.name],cwd=args.out,env=env,stdout=log,stderr=subprocess.STDOUT)
        launch=dict(started=datetime.now(timezone.utc).isoformat(),cpu=child_cpus(p),pid=p.pid,
                    sha256=sha256(exe.read_bytes()).hexdigest(),count=len(family),seed=520)
        assert launch['cpu']==[args.cpu]
        (args.out/'launch.json').write_text(json.dumps(launch,indent=2))
        result=p.wait()
    wall=time.perf_counter()-start
    memory=peak_bytes(p)
    if result: raise RuntimeError(result)
    log=(args.out/'solver.log').read_text(errors='replace')
    outputs=re.findall(r'(?ms)^CF_BEGIN_([0-9a-f]{4})\s*$\n(.*?)^CF_END_\1\s*$',log)
    assert [t for t,_ in outputs]==family, [len(outputs),len(family),log[:1500]]
    verified=[]
    for t,chunk in outputs:
        receipt=re.search(r'FRONTIER lower=(\d+) paid_wires=(\d+) projected=1',chunk)
        assert receipt,(t,chunk)
        lower,charged=map(int,receipt.groups())
        w=simulate(chunk,4,int(t,16))
        assert w['activity']==reference[t]['lower']==reference[t]['upper']==lower
        assert w['gates']==charged+1
        verified.append(w)
    report=dict(launch,wall_s=wall,peak_bytes=memory,exit_code=result,
                table_audit_sha256=sha256(args.audit.read_bytes()).hexdigest(),
                log_sha256=sha256((args.out/'solver.log').read_bytes()).hexdigest(),
                verified=len(verified),witnesses=verified)
    (args.out/'result.json').write_text(json.dumps(report,indent=2))
    print(len(verified),wall,memory)
