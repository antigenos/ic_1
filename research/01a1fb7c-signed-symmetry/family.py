"""Run and audit the preregistered, same-core census of F/H/N on four-input functions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from math import exp,fsum,log
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

from check_symmetry import HERE,leaders
from summarize import replay

ROOT=HERE.parents[1]
PUBLIC=HERE/"family-208"
WORK=ROOT/".local"/HERE.name/"family-208"
CPUS=tuple(range(4,28,2))


def write_once(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data:
            raise ValueError(f"Existing artifact differs: {path}")
        return
    with path.open("xb") as f:
        f.write(data)


def source():
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        members=json.loads(z.read("evidence/npn-family.json"))["essential"]
        history={t:set() for t in members}
        historic_time={}
        for method in ("author","support","both"):
            for line in z.read(f"evidence/e14-main/{method}.jsonl").splitlines():
                row=json.loads(line)
                t=row["experiment"]["truth"]
                if "witness" in row:
                    history[t].add(row["witness"]["activity"])
                if method=="both":
                    historic_time[t]=row["capped_wall_s"]
    return members,history,historic_time


def plan(members,historic_time,cpus):
    # Balance using only the earlier frozen F measurements.
    weights=dict.fromkeys(cpus,0.0)
    placement={}
    for t in sorted(members,key=lambda t:(-historic_time[t],t)):
        cpu=min(cpus,key=lambda c:(weights[c],c))
        weights[cpu]+=historic_time[t]
        placement[t]=cpu
    orders=("FHN","HNF","NFH","FNH","NHF","HFN")
    rows=[]
    for i,t in enumerate(members):
        v=int(t,16)
        rows.append(dict(truth=t,cpu=placement[t],order=orders[i%len(orders)],seconds=300,
                         signed_stricter=len(leaders(v,True))<len(leaders(v,False))))
    assert len(rows)==len(set(members))==208
    return rows


def verify_row(path,r,expected):
    rows=replay(path,r["truth"],r["order"],r["cpu"],r["seconds"])
    for entry in rows:
        assert entry["binary_sha256"]==expected[entry["experiment"]["arm"]]
        if entry["status"]=="timeout":
            assert entry["wall_s"]>=r["seconds"]-0.01
        discarded=entry.get("discarded_timeout_attempt")
        if discarded:
            assert discarded["status"]=="timeout" and discarded["experiment"]==entry["experiment"]
            assert discarded["wall_s"]>r["seconds"]+3 and discarded["binary_sha256"]==entry["binary_sha256"]
            assert sha256(discarded["solver_output"].encode()).hexdigest()==discarded["solver_log_sha256"]
    return rows


def timing_account(data,public):
    kept=[e for case in data.values() for e in case.values()]
    rejected=[e["discarded_timeout_attempt"] for e in kept if "discarded_timeout_attempt" in e]
    for f in sorted((public/"recovery").glob("*.json")):
        item=json.loads(f.read_bytes())["discarded"]
        assert item["status"]=="timeout" and item["wall_s"]>item["timeout_s"]+3
        rejected.extend([item["discarded_timeout_attempt"]] if "discarded_timeout_attempt" in item else [])
        rejected.append(item)
    return dict(accepted_original_wall_s=fsum(e["wall_s"] for e in kept),
                additional_discarded_wall_s=fsum(e["wall_s"] for e in rejected),
                discarded=[dict(truth=e["experiment"]["truth"],arm=e["experiment"]["arm"],wall_s=e["wall_s"],
                                start_utc=e["start_utc"]) for e in rejected])


def run_lane(rows,args,hashes):
    for r in rows:
        t=r["truth"]
        result=args.work/(t+".jsonl")
        if result.exists():
            count=len(result.read_text().splitlines())
            if count==len(r["order"]):
                verify_row(result,r,hashes)
                continue
            if not args.resume_id:
                raise RuntimeError(f"Incomplete {t}, inspect recorded PIDs and choose a new resume identifier")
        command=[sys.executable,str(HERE/"compare.py"),t,r["order"],str(result),"--prepared",str(args.prepared.resolve()),
                 "--raw-root",str(args.work/"raw"),"--cpu",str(r["cpu"]),"--cap",str(r["seconds"])]
        if args.resume_id:
            command+=["--resume-id",args.resume_id]
        with (args.work/(t+".launcher.log")).open("ab") as logf:
            subprocess.run(command,stdout=logf,stderr=subprocess.STDOUT,check=True)
        verify_row(result,r,hashes)
        print(f"Complete {t} CPU {r['cpu']}",flush=True)


def metrics(data):
    totals={}
    comparisons={}
    for arm in "FHN":
        rows=[v[arm] for v in data.values()]
        totals[arm]=dict(completed=sum("witness" in r for r in rows),capped_s=fsum(r["capped_wall_s"] for r in rows))
        if arm=="N": continue
        ratios={t:v[arm]["wall_s"]/v["N"]["wall_s"] for t,v in data.items()
                if all("witness" in v[a] for a in (arm,"N"))}
        comparisons[arm]=dict(common=len(ratios),gm=exp(fsum(map(log,ratios.values()))/len(ratios)) if ratios else None,
                              gained=[t for t,v in data.items() if "witness" in v["N"] and "witness" not in v[arm]],
                              lost=[t for t,v in data.items() if "witness" in v[arm] and "witness" not in v["N"]],
                              slower=[t for t,k in ratios.items() if k<1],ratios=ratios)
    return dict(functions=len(data),totals=totals,baseline_over_N=comparisons)


def audit(rows,hashes,history,public,work,export):
    from tempfile import TemporaryDirectory
    data={}
    certificate_path=HERE/"prefix-560.json"
    certified=json.loads(certificate_path.read_bytes())["certificates"] if certificate_path.exists() else None
    independent_matches=0
    above_threshold=0
    with TemporaryDirectory() as folder:
        if not export:
            # Restore byte-identical per-target input for the original log verifier.
            members=(public/"runs.jsonl").read_bytes().splitlines(keepends=True)
            if len(members)!=3*len(rows): raise ValueError("Incomplete published census")
            work=Path(folder)
            for i,r in enumerate(rows):
                (work/(r["truth"]+".jsonl")).write_bytes(b"".join(members[3*i:3*i+3]))
        raw=[]
        for r in rows:
            t=r["truth"]
            path=work/(t+".jsonl")
            verified=verify_row(path,r,hashes)
            vals={e["witness"]["activity"] for e in verified if "witness" in e}
            assert len(vals|history[t])<=1
            if certified is not None and vals:
                if certified[t] is None:
                    assert min(vals)>560
                    above_threshold+=1
                else:
                    assert vals=={certified[t]}
                    independent_matches+=1
            data[t]={e["experiment"]["arm"]:e for e in verified}
            raw.extend(path.read_bytes().splitlines())
        stream=b"\n".join(raw)+b"\n"
    summary=metrics(data)
    summary["measurement_account"]=timing_account(data,public)
    if certified is not None:
        summary["distinct_solved_functions_with_independent_exact_proof"]=independent_matches
        summary["distinct_solved_functions_above_proof_bound"]=above_threshold
    summary.update(verified_witnesses=sum(m["completed"] for m in summary["totals"].values()),
                   raw_sha256=sha256(stream).hexdigest(),runs=len(raw))
    for strict,key in ((True,"stricter"),(False,"identical")):
        summary[key]=metrics({r["truth"]:data[r["truth"]] for r in rows if r["signed_stricter"]==strict})
    summary_bytes=(json.dumps(summary,indent=2)+"\n").encode()
    if export:
        write_once(public/"runs.jsonl",stream)
        write_once(public/"summary.json",summary_bytes)
    else:
        assert json.loads((public/"summary.json").read_bytes())==summary
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("plan","run","export","verify"))
    p.add_argument("--public",type=Path,default=PUBLIC)
    p.add_argument("--work",type=Path,default=WORK)
    p.add_argument("--prepared",type=Path,default=ROOT)
    p.add_argument("--cpus",type=int,nargs="+",default=CPUS)
    p.add_argument("--resume-id")
    args=p.parse_args()
    if min(args.cpus)<0 or len(set(args.cpus))!=len(args.cpus): p.error("Invalid CPU list")
    members,history,historic_time=source()
    rows=plan(members,historic_time,args.cpus)
    manifest=args.public/"manifest.json"
    if args.action in ("plan","run"):
        import os
        exe="abc.exe" if os.name=="nt" else "abc"
        f=sha256((args.prepared/".local/variants/joint"/exe).read_bytes()).hexdigest()
        n=sha256((ROOT/".local/variants/signed-symmetry-confirmed-01a1fb7c"/exe).read_bytes()).hexdigest()
        hashes={"F":f,"H":n,"N":n}
        protocol=dict(binary_sha256=hashes,cpus=list(args.cpus),rows=rows)
        if args.action=="plan":
            write_once(manifest,(json.dumps(protocol,indent=2)+"\n").encode())
            predicted=max(sum(historic_time[r["truth"]]*3 for r in rows if r["cpu"]==c) for c in args.cpus)
            maximum=900*max(sum(r["cpu"]==c for r in rows) for c in args.cpus)
            print(f"Targets {len(rows)}, lanes {len(args.cpus)}, historic-cost estimate {predicted/3600:.2f} h, cap {maximum/3600:.2f} h")
            return
        assert json.loads(manifest.read_bytes())==protocol
        args.work.mkdir(parents=True,exist_ok=True)
        with ThreadPoolExecutor(max_workers=len(args.cpus)) as pool:
            jobs=[pool.submit(run_lane,[r for r in rows if r["cpu"]==c],args,hashes) for c in args.cpus]
            for job in jobs: job.result()
        print("All 624 measurements verified",flush=True)
    else:
        m=json.loads(manifest.read_bytes())
        assert m["rows"]==rows and m["cpus"]==list(args.cpus)
        result=audit(rows,m["binary_sha256"],history,args.public,args.work,args.action=="export")
        print(json.dumps({k:result[k] for k in ("runs","verified_witnesses","totals","raw_sha256")}))


if __name__=="__main__":
    main()
