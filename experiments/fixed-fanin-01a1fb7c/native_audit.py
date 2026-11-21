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


def previous_case(pristine, name):
    if pristine is not None:
        case=pristine/name
        if (case/"result.json").is_file() and json.loads((case/"result.json").read_text())["status"]=="solver_completed_verified_witness":
            return case
    return None


def work(rows, binary, dest, cpu, pristine=None):
    pin(cpu)
    binary_hash=hashlib.sha256(binary.read_bytes()).hexdigest()
    for row in rows:
        circuit=spec(row)
        sha=hashlib.sha256(circuit.encode()).hexdigest()
        name=row["truth"]+"-"+sha[:12]
        old=previous_case(pristine,name)
        if old:
            saved=json.loads((old/"result.json").read_text())
            assert saved["experiment"]["certificate"]==sha
            verify(row,(old/"solver.log").read_text())
            continue
        case=dest/name
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


def archive(rows, dest, output, pristine=None):
    output.mkdir(parents=True,exist_ok=True)
    parts=[]
    for row in rows:
        sha=hashlib.sha256(spec(row).encode()).hexdigest()
        name=row["truth"]+"-"+sha[:12]
        old=previous_case(pristine,name)
        case=old or dest/name
        result=json.loads((case/"result.json").read_text())
        raw=(case/"solver.log").read_bytes()
        verify(row,raw.decode())
        assert result["experiment"]["certificate"]==sha and result["status"]=="solver_completed_verified_witness"
        build="pristine" if old or pristine is None else "equivalent_histogram_enumerator"
        parts.append(dict(result,validation_build=build,solver_output=raw.decode(),solver_log_sha256=hashlib.sha256(raw).hexdigest()))
    for start in range(0,len(parts),26):
        data=parts[start:start+26]
        (output/f"part-{start//26+1:02}.jsonl").write_text("".join(json.dumps(x,separators=(",",":"))+"\n" for x in data),encoding="utf-8")
    if pristine:
        attempts=[]
        for path in sorted(pristine.glob("*/result.json")):
            row=json.loads(path.read_text())
            if row["status"]!="solver_completed_verified_witness":
                attempts.append(dict(row,solver_output=(path.parent/"solver.log").read_text()))
        (output/"pristine-incomplete.json").write_text(json.dumps(attempts,indent=2)+"\n")
    print("DATE CNF confirmed",len(parts),"complete circuits.",flush=True)


def verify_archive(rows, folder):
    all_runs=[json.loads(line) for part in sorted(folder.glob("part-*.jsonl"))
              for line in part.read_text(encoding="utf-8").splitlines()]
    identities={}
    for circuit,record in zip(rows,all_runs,strict=True):
        assert record["experiment"]["certificate"]==hashlib.sha256(spec(circuit).encode()).hexdigest()
        assert record["child_affinity"]==[record["experiment"]["cpu"]]
        assert record["command"][1:]==["-c","pexact -I 4 -M 2 "+circuit["truth"]]
        assert record["status"]=="solver_completed_verified_witness" and record["returncode"]==0
        message=record["solver_output"]
        assert hashlib.sha256(message.encode()).hexdigest()==record["solver_log_sha256"]
        verify(circuit,message)
        variant=record["validation_build"]
        assert variant in ("pristine","equivalent_histogram_enumerator")
        assert identities.setdefault(variant,record["binary_sha256"])==record["binary_sha256"]
    print("Verified",len(all_runs),"native logs and exact gate lists.")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("library",type=Path)
    p.add_argument("directory",type=Path,nargs="?")
    p.add_argument("--cpus",nargs="+",type=int)
    p.add_argument("--export",type=Path)
    p.add_argument("--verify-export",type=Path)
    p.add_argument("--reuse-pristine",type=Path,help="Reuse passed original runs and use the equivalent histogram generator for pending certificates")
    args=p.parse_args()
    data=json.loads(args.library.read_text())
    assert check(data)==data["verified"]
    rows=[r for r in data["circuits"] if r["activity"]>=0]
    if args.verify_export:
        verify_archive(rows,args.verify_export)
        sys.exit(0)
    if args.directory is None or not args.cpus:
        p.error("An output directory and --cpus are required to run the native checker")
    kind="library-check-fast" if args.reuse_pristine else "library-check"
    binary=ROOT/".local/variants"/("fixed-fanin-"+kind)/("abc.exe" if os.name=="nt" else "abc")
    args.directory.mkdir(parents=True,exist_ok=True)
    assert len(set(args.cpus))==len(args.cpus)
    with ProcessPoolExecutor(max_workers=len(args.cpus)) as pool:
        jobs=[pool.submit(work,rows[i::len(args.cpus)],binary,args.directory,cpu,args.reuse_pristine) for i,cpu in enumerate(args.cpus)]
        for job in jobs: job.result()
    if args.export: archive(rows,args.directory,args.export,args.reuse_pristine)
