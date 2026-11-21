"""Run, resume and independently audit a paired all-family comparison."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import contextlib
from datetime import datetime
import hashlib
import json
from math import exp, isclose, log
import os
from pathlib import Path
from statistics import mean
import sys
from zipfile import ZIP_DEFLATED, ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"tools"))
from repeat_0189 import pin
from run_case import run
from witness import simulate

VERIFIED="solver_completed_verified_witness"
CAP=300


def binary_paths(frozen):
    exe="abc.exe" if os.name=="nt" else "abc"
    return {"A":frozen/".local/variants/joint"/exe,"C":HERE/".local/build-saved"/exe}


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def original():
    with ZipFile(HERE/"final-reproduction.zip") as z:
        return [json.loads(s) for s in z.read("evidence/e14-main/both.jsonl").splitlines()]


def reused():
    a,c = (HERE/"evidence/hard-018b.jsonl").read_bytes().splitlines()[-1], (HERE/"evidence/hard-saved-018b.jsonl").read_bytes()
    return {"A":json.loads(a),"C":json.loads(c)}


def plan(frozen,cpus):
    refs=original()
    hashes={k:digest(v) for k,v in binary_paths(frozen).items()}
    prior=reused()
    reuse=all(v["binary_sha256"]==hashes[k] and v["timeout_s"]==CAP for k,v in prior.items())
    loads={c:0.0 for c in cpus}
    index={r["experiment"]["truth"]:i for i,r in enumerate(refs)}
    picks=[]
    for r in sorted(refs,key=lambda v:(-v["capped_wall_s"],v["experiment"]["truth"])):
        t=r["experiment"]["truth"]
        if t=="018b" and reuse:
            picks.append(dict(truth=t,cpu=28,order="AC",source="completed-hard-pair"))
            continue
        cpu=min(cpus,key=lambda c:(loads[c],c))
        loads[cpu]+=r["capped_wall_s"]
        picks.append(dict(truth=t,cpu=cpu,order="AC" if index[t]%2==0 else "CA",source="new"))
    assert len(picks)==len(index)==208
    # Mix long and short cases reproducibly after balancing lanes by expected cost.
    picks.sort(key=lambda row:hashlib.sha256(("full-9720/"+row["truth"]).encode()).digest())
    return dict(cap=CAP,methods={"A":"frozen TCJAP","C":"saved witness and strict residual ranges"},
                binary_sha256=hashes,cpus=cpus,cases=picks)


@contextlib.contextmanager
def lane_lock(path):
    with path.open("a+b") as f:
        if not f.tell():
            f.write(b"x"); f.flush()
        f.seek(0)
        if os.name=="nt":
            import msvcrt
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def validate(row,case,arm,hashes):
    t=case["truth"]
    assert row["binary_sha256"]==hashes[arm] and row["timeout_s"]==CAP
    assert row["command"][1:]==["-c",f"pexact -I 4 -M 2 {t}"]
    assert row["child_affinity"]==[case["cpu"]]
    assert row["experiment"]["truth"]==t and row["experiment"]["arm"]==arm
    assert row["pid"]>0 and 0<row["wall_s"]<=CAP+3
    assert isclose(row["capped_wall_s"],min(row["wall_s"],CAP))
    assert hashlib.sha256(row["solver_output"].encode()).hexdigest()==row["solver_log_sha256"]
    if row["status"]==VERIFIED:
        assert row["returncode"]==0 and row["wall_s"]<=CAP
        assert simulate(row["solver_output"],4,int(t,16))==row["witness"]
    else:
        assert row["status"]=="timeout" and "witness" not in row and row["wall_s"]>=CAP-0.05


def read_case(path):
    row=json.loads((path/"result.json").read_bytes())
    raw=(path/"solver.log").read_bytes()
    row.update(solver_output=raw.decode(),solver_log_sha256=hashlib.sha256(raw).hexdigest())
    return row


def run_lane(cpu,manifest,work,frozen):
    pin(cpu)
    bins=binary_paths(frozen)
    env={k:v for k,v in os.environ.items() if not k.startswith(("REPLAY_","OPTWIN_"))}
    with lane_lock(work/f"lane-{cpu}.lock"):
        for case in manifest["cases"]:
            if case["source"]!="new" or case["cpu"]!=cpu:
                continue
            t=case["truth"]
            for i,arm in enumerate(case["order"],1):
                path=work/t/arm
                if not (path/"result.json").exists():
                    if path.exists():
                        raise RuntimeError(f"Inspect incomplete existing solver before resuming: {path}")
                    run(bins[arm],t,4,2,CAP,path,env=env,
                        metadata=dict(truth=t,arm=arm,cpu=cpu,order=i,cohort="family-300"))
                row=read_case(path)
                validate(row,case,arm,manifest["binary_sha256"])
                receipt=path/"verified.json"
                if not receipt.exists():
                    tmp=path/"verified.tmp"
                    tmp.write_text(json.dumps({"status":row["status"],"wall_s":row["wall_s"]}))
                    tmp.replace(receipt)


def check_plan(m):
    truths=[x["experiment"]["truth"] for x in original()]
    assert len(m["cases"])==len(truths)==208 and {c["truth"] for c in m["cases"]}==set(truths)
    assert m["cap"]==CAP and set(m["binary_sha256"])=={"A","C"}
    assert all(c["order"] in ("AC","CA") for c in m["cases"])


def guarded_lane(cpu,manifest,work,frozen):
    error_path=work/f"error-{cpu}.json"
    try:
        run_lane(cpu,manifest,work,frozen)
    except Exception as exc:
        error_path.write_text(json.dumps(dict(cpu=cpu,error=repr(exc))),encoding="utf8")
        raise


def summarize(rows,manifest):
    by_arm={arm:{r["experiment"]["truth"]:r for r in group} for arm,group in rows.items()}
    out={}
    for arm,g in by_arm.items():
        assert len(g)==len(rows[arm])==208
        out[arm]=dict(completed=sum(r["status"]==VERIFIED for r in g.values()),
                      capped_s=sum(r["capped_wall_s"] for r in g.values()))
    ratios, gained,lost={},[],[]
    known={}
    with ZipFile(HERE/"final-reproduction.zip") as z:
        for arm in ("author","both","support"):
            for line in z.read("evidence/e14-main/"+arm+".jsonl").splitlines():
                old=json.loads(line)
                if "witness" in old:
                    key=old["experiment"]["truth"]
                    assert known.setdefault(key,old["witness"]["activity"])==old["witness"]["activity"]
    for case in manifest["cases"]:
        t=case["truth"]
        a,c=(by_arm[k][t] for k in "AC")
        for k,row in (("A",a),("C",c)):
            validate(row,case,k,manifest["binary_sha256"])
            if "witness" in row:
                assert known.setdefault(t,row["witness"]["activity"])==row["witness"]["activity"]
        first,second=(by_arm[k][t] for k in case["order"])
        diff=(datetime.fromisoformat(second["start_utc"])-datetime.fromisoformat(first["start_utc"])).total_seconds()
        assert diff+0.1>=first["wall_s"],(t,"overlapping pair")
        if a["status"]==c["status"]==VERIFIED:
            ratios[t]=a["wall_s"]/c["wall_s"]
        elif a["status"]!=c["status"]:
            (gained if c["status"]==VERIFIED else lost).append(t)
    return dict(functions=208,validated_trials=416,methods=out,common=len(ratios),
                paired_gm=exp(mean(log(x) for x in ratios.values())) if ratios else None,
                gained=sorted(gained),lost=sorted(lost),slower={t:x for t,x in ratios.items() if x<1},
                ratios=ratios)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("plan","run","status","pack","audit"))
    p.add_argument("frozen",type=Path)
    p.add_argument("--cpus",nargs="+",type=int,default=[4,6,8,10,14])
    p.add_argument("--manifest",type=Path,default=HERE/"evidence/family-plan.json")
    p.add_argument("--work",type=Path,default=HERE/".local/full-300")
    p.add_argument("--archive",type=Path,default=HERE/"evidence/family-300.zip")
    args=p.parse_args()
    if args.action=="plan":
        assert len(set(args.cpus))==len(args.cpus) and args.cpus
        m=plan(args.frozen.resolve(),args.cpus)
        with args.manifest.open("x") as f:
            json.dump(m,f,indent=2);f.write("\n")
        return
    m=json.loads(args.manifest.read_bytes())
    check_plan(m)
    work=args.work.resolve()
    if args.action=="run":
        assert {k:digest(v) for k,v in binary_paths(args.frozen.resolve()).items()}==m["binary_sha256"]
        work.mkdir(parents=True,exist_ok=True)
        with ProcessPoolExecutor(max_workers=len(m["cpus"])) as pool:
            tasks=[pool.submit(guarded_lane,c,m,work,args.frozen.resolve()) for c in m["cpus"]]
            for task in tasks:
                task.result()
    elif args.action=="status":
        files=list(work.glob("*/*/verified.json"))
        retained=2*sum(c["source"]!="new" for c in m["cases"])
        counts=Counter(json.loads(f.read_bytes())["status"] for f in files)
        print(json.dumps(dict(verified=len(files)+retained,reused=retained,new_status=counts,
                              pending=416-retained-len(files),
                              errors=[json.loads(f.read_bytes()) for f in work.glob("error-*.json") ])))
    else:
        rows={"A":[],"C":[]}
        if args.action=="pack":
            for c in m["cases"]:
                for arm in "AC":
                    row=reused()[arm] if c["source"]!="new" else read_case(work/c["truth"]/arm)
                    rows[arm].append(row)
            result=summarize(rows,m)
            with ZipFile(args.archive,"x",compression=ZIP_DEFLATED) as z:
                z.writestr("manifest.json",args.manifest.read_bytes())
                for arm in "AC":
                    z.writestr(arm+".jsonl","".join(json.dumps(row)+"\n" for row in rows[arm]))
                z.writestr("summary.json",json.dumps(result,indent=2)+"\n")
        else:
            with ZipFile(args.archive) as z:
                assert json.loads(z.read("manifest.json"))==m
                rows={arm:[json.loads(s) for s in z.read(arm+".jsonl").splitlines()] for arm in "AC"}
                result=summarize(rows,m)
                assert result==json.loads(z.read("summary.json"))
        print(json.dumps({k:v for k,v in result.items() if k not in ("ratios","slower")}))


if __name__=="__main__":
    main()
