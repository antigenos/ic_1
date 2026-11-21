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
from check_symmetry import MAPS,OPS,PINS,gate,norm,transform
from witness import simulate


def replay_constructed(target,cost,image,parts):
    rows=next(m for _,m in MAPS if transform(image,m)==norm(target))
    names={p:chr(97+i) for i,p in enumerate(PINS)}
    text=[f"Realization of given 4-input function using {len(parts)} two-input gates complementary={target&1}:"]
    for i,part in enumerate(parts,4):
        a,b,x=[transform(int(v,16),rows) for v in part.split(",")]
        op=next(o for o in OPS if gate(o,a,b)==x)
        if i==3+len(parts) and target&1: op^=15
        text.append(f"{i:02d} = 4'b{op:04b}( {names[a]} {names[b]} )")
        names[x]=f"{i:02d}"
    text.append(f"Switching Activity={cost}")
    log="\n".join(text)+"\n"
    return dict(witness=simulate(log,4,target),circuit=log)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cap",type=int,required=True)
    p.add_argument("--max-states",type=int,default=6000000)
    p.add_argument("--cpu",type=int,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--mode",choices=("raw","orbit","prefix"),help="recover circuits with no, first or continuing symmetry")
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
        opts=[args.mode] if args.mode else []
        rows=subprocess.check_output([str(binary),str(args.cap),str(args.max_states),*opts],text=True,
                                     input="\n".join(members)+"\n").splitlines()
        process_s=perf_counter()-start
    label,cap,states,seconds=rows[0].split()
    assert label=="C" and int(cap)==args.cap and len(rows)==209
    if args.mode in (None,"raw") and args.cap in (302,366):
        assert int(states)=={302:16950,366:196250}[args.cap]
    values={}
    circuits={}
    corroborated=0
    for t,line in zip(members,rows[1:]):
        key,value,*rest=line.split()
        assert int(key,16)==int(t,16)
        cost=int(value)
        if args.mode and cost>=0:
            circuits[t]=replay_constructed(int(t,16),cost,int(rest[0],16),rest[1:])
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
    if args.mode:
        if args.cap in (302,366,440):
            assert values==json.loads((HERE/f"closure-{args.cap}.json").read_bytes())["certificates"]
        if args.mode=="prefix" and args.cap==500:
            assert values==json.loads((HERE/"orbit-500.json").read_bytes())["certificates"]
        report.update(mode=args.mode,verified_circuits=circuits)
    with args.output.open("x",encoding="utf-8") as f:
        json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in ("certificates","verified_circuits")}))


if __name__=="__main__":
    main()
