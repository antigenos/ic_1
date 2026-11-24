"""Exercise the TCJAP command entry, signed targets, and unrecognized fallback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from run import digest,pin
from synthesize import solution

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/"tools"))
from witness import simulate


def execute(binary,targets):
    env={k:v for k,v in os.environ.items() if not k.startswith(("FF_","REPLAY_"))}
    cmd="; ".join(f"pexact -I 4 -M 2 {t:04x}" for t in targets)
    start=time.perf_counter()
    run=subprocess.run([str(binary.resolve()),"-c",cmd],env=env,capture_output=True,
                       text=True,timeout=45,check=True)
    return run.stdout,time.perf_counter()-start


def main():
    p=argparse.ArgumentParser()
    for key in ("frozen","candidate","output"):
        p.add_argument(key,type=Path)
    args=p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    pin(24)
    expected={}
    for t in range(65536):
        answer=solution(4,t)
        if answer:
            ep=answer["endpoints"][-1]
            expected[t]={"truth":f"{t:04x}","activity":ep["activity"],"gates":ep["gate_count"]}
    assert len(expected)==416
    targets=sorted(expected)
    batches=[]
    transcript=hashlib.sha256()
    for i in range(0,len(targets),32):
        group=targets[i:i+32]
        out,elapsed=execute(args.candidate,group)
        _,*blocks=out.split("PARETO_CERTIFIED")
        assert len(blocks)==len(group)
        for t,block in zip(group,blocks):
            assert simulate(block,4,t)==expected[t]
        transcript.update(out.encode())
        batches.append(elapsed)
    # All distinct covered classes, then two unrecognized positive controls.
    costs={1:152,7:182,0x7f:152,0x1fe:152,6:208,0x1b:304}
    pairs=[]
    for j,(t,cost) in enumerate(costs.items()):
        observations={}
        for idx in (j%2,1-j%2):
            label,binary=(("frozen",args.frozen),("candidate",args.candidate))[idx]
            out,elapsed=execute(binary,[t])
            w=simulate(out,4,t)
            assert w["activity"]==cost and ("PARETO_CERTIFIED" in out)==(t in expected and idx==1)
            observations[label]=dict(wall_s=elapsed,witness=w,stdout=out)
        pairs.append(dict(truth=f"{t:04x}",observations=observations))
    report=dict(cpu=24,targets=len(targets),batches_wall_s=batches,
                batch_transcript_sha256=transcript.hexdigest(),frozen_sha256=digest(args.frozen),
                candidate_sha256=digest(args.candidate),pairs=pairs)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print("Verified",len(expected),"signed targets and",len(pairs),"paired cold controls.")


if __name__=="__main__":
    main()
