"""Compare a complete cost-bounded enumeration with the original logged witnesses."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

from family import HERE, source
from repeat_0189 import pin


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cap",type=int,required=True)
    p.add_argument("--max-states",type=int,default=6000000)
    p.add_argument("--cpu",type=int,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.output.exists(): p.error("Use a new certificate file")
    pin(args.cpu)
    members,history,_=source()
    holdout=json.loads((HERE/"confirmation/summary.json").read_text())["cases"]
    for t,arms in holdout.items():
        history[t].update(r["activity"] for r in arms.values() if r["activity"] is not None)
    with TemporaryDirectory() as folder:
        binary=Path(folder)/("closure.exe" if os.name=="nt" else "closure")
        cpp=HERE/"cost_closure.cpp"
        start=perf_counter()
        subprocess.run(["g++","-O3","-std=c++17",str(cpp),"-o",str(binary)],check=True)
        compile_s=perf_counter()-start
        start=perf_counter()
        rows=subprocess.check_output([str(binary),str(args.cap),str(args.max_states)],text=True,
                                     input="\n".join(members)+"\n").splitlines()
        process_s=perf_counter()-start
    label,cap,states,seconds=rows[0].split()
    assert label=="C" and int(cap)==args.cap and len(rows)==209
    if args.cap in (302,366):
        assert int(states)=={302:16950,366:196250}[args.cap]
    values={}
    corroborated=0
    for t,line in zip(members,rows[1:]):
        key,value=line.split()
        assert int(key,16)==int(t,16)
        cost=int(value)
        if history[t]:
            assert len(history[t])==1
            archived=next(iter(history[t]))
            if archived<=args.cap:
                assert archived==cost,(t,cost,archived)
                corroborated+=1
            else:
                assert cost==-1,(t,cost,archived)
        values[t]=None if cost==-1 else cost
    report=dict(limit=args.cap,states=int(states),enumeration_s=float(seconds),process_s=process_s,compile_s=compile_s,
                cpu=args.cpu,source_sha256=sha256(cpp.read_bytes()).hexdigest(),witnessed_minima_matched=corroborated,
                finite_minima=sum(v is not None for v in values.values()),certificates=values)
    with args.output.open("x",encoding="utf-8") as f:
        json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!="certificates"}))


if __name__=="__main__":
    main()
