"""Check library certificates in the original SAT encoding and replay the exact returned wiring."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from repeat_0189 import pin
from run_case import run
from witness import GATE,simulate
from library import check


def spec(row):
    target=int(row["truth"],16)
    normalized=target ^ (65535 if target & 1 else 0)
    values=[normalized,row["activity"],len(row["gates"])]
    for g in row["gates"]: values.extend(g)
    return " ".join(map(str,values))


def verify(row, text):
    assert "FF_ORIGINAL_CNF verified" in text and "Total runtime" in text
    t=int(row["truth"],16)
    assert simulate(text,4,t)==dict(truth=row["truth"],activity=row["activity"],gates=len(row["gates"]))
    actual=sorted(GATE.findall(text.replace("\r","")),key=lambda g:int(g[0]))
    def index(name):
        return int(name) if name.isdigit() else ord(name)-ord("a")
    for i,(gate,(hi,lo,code)) in enumerate(zip(actual,row["gates"],strict=True)):
        out, printed, first,second=gate
        original_op=(code&9)|((code&2)<<1)|((code&4)>>1)
        if i==len(actual)-1 and row["complement"]: original_op ^= 15
        assert (int(out),int(printed,2),index(first),index(second))==(4+i,original_op,lo,hi)


def work(rows, binary, dest, cpu):
    pin(cpu)
    binary_hash=hashlib.sha256(binary.read_bytes()).hexdigest()
    for row in rows:
        circuit=spec(row)
        sha=hashlib.sha256(circuit.encode()).hexdigest()
        case=dest/(row["truth"]+"-"+sha[:12])
        if (case/"result.json").exists():
            r=json.loads((case/"result.json").read_text())
            assert r["binary_sha256"]==binary_hash and r["experiment"]["certificate"]==sha
        else:
            env={k:v for k,v in os.environ.items() if not k.startswith(("FF_","REPLAY_"))}
            env["FF_LIBRARY"]=circuit
            r=run(binary,row["truth"],4,2,90,case,env=env,metadata={"cpu":cpu,"certificate":sha})
        if r["status"]!="solver_completed_verified_witness":
            raise ValueError(f"Native certificate validation failed at {case}")
        verify(row,(case/"solver.log").read_text())


def archive(rows, dest, output):
    output.mkdir(parents=True,exist_ok=True)
    parts=[]
    for row in rows:
        sha=hashlib.sha256(spec(row).encode()).hexdigest()
        case=dest/(row["truth"]+"-"+sha[:12])
        result=json.loads((case/"result.json").read_text())
        raw=(case/"solver.log").read_bytes()
        verify(row,raw.decode())
        assert result["experiment"]["certificate"]==sha and result["status"]=="solver_completed_verified_witness"
        parts.append(dict(result,solver_output=raw.decode(),solver_log_sha256=hashlib.sha256(raw).hexdigest()))
    for start in range(0,len(parts),26):
        data=parts[start:start+26]
        (output/f"part-{start//26+1:02}.jsonl").write_text("".join(json.dumps(x,separators=(",",":"))+"\n" for x in data),encoding="utf-8")
    print("Original DATE CNF confirmed",len(parts),"complete circuits.",flush=True)


def verify_archive(rows, folder):
    all_runs=[json.loads(line) for part in sorted(folder.glob("part-*.jsonl"))
              for line in part.read_text(encoding="utf-8").splitlines()]
    identities=set()
    for circuit,record in zip(rows,all_runs,strict=True):
        assert record["experiment"]["certificate"]==hashlib.sha256(spec(circuit).encode()).hexdigest()
        assert record["child_affinity"]==[record["experiment"]["cpu"]]
        assert record["command"][1:]==["-c","pexact -I 4 -M 2 "+circuit["truth"]]
        assert record["status"]=="solver_completed_verified_witness" and record["returncode"]==0
        message=record["solver_output"]
        assert hashlib.sha256(message.encode()).hexdigest()==record["solver_log_sha256"]
        verify(circuit,message)
        identities.add(record["binary_sha256"])
    assert len(identities)==1
    print("Verified",len(all_runs),"native logs and exact gate lists.")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("library",type=Path)
    p.add_argument("directory",type=Path,nargs="?")
    p.add_argument("--cpus",nargs="+",type=int)
    p.add_argument("--export",type=Path)
    p.add_argument("--verify-export",type=Path)
    args=p.parse_args()
    data=json.loads(args.library.read_text())
    assert check(data)==data["verified"]
    rows=[r for r in data["circuits"] if r["activity"]>=0]
    if args.verify_export:
        verify_archive(rows,args.verify_export)
        sys.exit(0)
    if args.directory is None or not args.cpus:
        p.error("An output directory and --cpus are required to run the native checker")
    binary=ROOT/".local/variants/fixed-fanin-library-check"/("abc.exe" if os.name=="nt" else "abc")
    args.directory.mkdir(parents=True,exist_ok=True)
    assert len(set(args.cpus))==len(args.cpus)
    with ProcessPoolExecutor(max_workers=len(args.cpus)) as pool:
        jobs=[pool.submit(work,rows[i::len(args.cpus)],binary,args.directory,cpu) for i,cpu in enumerate(args.cpus)]
        for job in jobs: job.result()
    if args.export: archive(rows,args.directory,args.export)
