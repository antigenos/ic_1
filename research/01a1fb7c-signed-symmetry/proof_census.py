"""Balanced cold-process confirmation of proof transfer against the identical ABC binary."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from math import exp,fsum,log
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from family import HERE,ROOT,run_lane,source,timing_account,verify_row,write_once


def cohort(kind,cpus):
    members,history,historic_time=source()
    exact=json.loads((HERE/"prefix-560.json").read_bytes())["certificates"]
    excluded={"0189","07b4","0016","0116","0118","066b"}
    for row in json.loads((HERE/"confirmation/manifest.json").read_bytes()):
        excluded.add(row["truth"])
    for row in json.loads((HERE/"order-validation.json").read_bytes())["cohort"]:
        excluded.add(row["truth"])
    def tier(t):
        v=exact[t]
        return 3 if v is None else 2 if v>500 else 1 if v>440 else 0
    if kind=="confirm":
        selected=[]
        def rank(t): return sha256(("01a1fb7c-proofconfirm-v1:"+t).encode()).digest()
        for k in range(4):
            pool=sorted((t for t in members if t not in excluded and tier(t)==k),key=rank)
            if k:
                selected.extend(pool[:3])
            else:
                for lo,hi in ((0,10),(10,300),(300,301)):
                    selected.append(next(t for t in pool if lo<=historic_time[t]<hi))
        assert len(set(selected))==12
    else:
        selected=members
    rows=[dict(truth=t,cpu=cpus[i%len(cpus)],order=("35","53")[i%2],seconds=300,tier=tier(t))
          for i,t in enumerate(selected)]
    # With an even number of lanes, alternate within each lane as well.
    for i,r in enumerate(rows):
        r["order"]=("35","53")[(i+i//len(cpus))%2]
    return rows,history,exact


def summarize(records):
    if not records: return {}
    result={}
    for arm in "35":
        group=[v[arm] for v in records.values()]
        result[arm]=dict(completed=sum("witness" in row for row in group),capped_s=fsum(row["capped_wall_s"] for row in group))
    ratios={t:v["3"]["wall_s"]/v["5"]["wall_s"] for t,v in records.items()
            if all("witness" in v[a] for a in "35")}
    return dict(functions=len(records),totals=result,common=len(ratios),ratios=ratios,
                gm=exp(fsum(map(log,ratios.values()))/len(ratios)) if ratios else None,
                gained=[t for t,v in records.items() if "witness" in v["5"] and "witness" not in v["3"]],
                lost=[t for t,v in records.items() if "witness" in v["3"] and "witness" not in v["5"]])


def export_or_check(args,m,history,exact):
    rows=m["rows"]
    work=args.work
    with TemporaryDirectory() as temp:
        if args.action=="verify":
            work=Path(temp)
            stream=(args.public/"runs.jsonl").read_bytes().splitlines(keepends=True)
            assert len(stream)==2*len(rows)
            for i,r in enumerate(rows):
                (work/(r["truth"]+".jsonl")).write_bytes(b"".join(stream[2*i:2*i+2]))
        entries={}
        raw=[]
        statuses={}
        for r in rows:
            t=r["truth"]
            path=work/(t+".jsonl")
            pair=verify_row(path,r,m["binary_sha256"])
            raw.extend(path.read_bytes().splitlines())
            entries[t]={row["experiment"]["arm"]:row for row in pair}
            values={row["witness"]["activity"] for row in pair if "witness" in row}
            assert len(values|history[t])<=1
            if exact[t] is None:
                assert all(v>560 for v in values)
            else:
                assert not values or values=={exact[t]}
            cand=entries[t]["5"]
            logtext=cand["solver_output"]
            confirmed="PREFIX author_verified=pins" in logtext
            fallback="PREFIX author_search_from=" in logtext
            assert not (confirmed and fallback)
            if "witness" in cand:
                assert confirmed or fallback
                if confirmed:
                    assert f"PREFIX author_verified=pins cost={cand['witness']['activity']} gates={cand['witness']['gates']}" in logtext
            assert "PREFIX " not in entries[t]["3"]["solver_output"]
            statuses[t]="author_verified_pins" if confirmed else "author_search_from_bound" if fallback else "budget_expired_before_handoff"
    stream=b"\n".join(raw)+b"\n"
    summary=summarize(entries)
    summary["measurement_account"]=timing_account(entries,args.public)
    summary.update(runs=len(raw),raw_sha256=sha256(stream).hexdigest(),transfer_state=statuses)
    summary["by_tier"]={str(k):summarize({r["truth"]:entries[r["truth"]] for r in rows if r["tier"]==k}) for k in range(4)}
    if args.action=="export":
        write_once(args.public/"runs.jsonl",stream)
        write_once(args.public/"summary.json",(json.dumps(summary,indent=2)+"\n").encode())
    else:
        assert summary==json.loads((args.public/"summary.json").read_bytes())
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("plan","run","export","verify"))
    p.add_argument("--kind",choices=("confirm","full"),default="confirm")
    p.add_argument("--cpus",type=int,nargs="+",required=True)
    p.add_argument("--work",type=Path)
    p.add_argument("--public",type=Path)
    p.add_argument("--prepared",type=Path,default=ROOT)
    p.add_argument("--resume-id")
    args=p.parse_args()
    if len(set(args.cpus))!=len(args.cpus) or min(args.cpus)<0: p.error("Invalid CPU list")
    label="proof-"+args.kind
    args.public=args.public or HERE/label
    args.work=args.work or ROOT/".local"/HERE.name/label
    rows,history,exact=cohort(args.kind,args.cpus)
    manifest=args.public/"manifest.json"
    if args.action in ("plan","run"):
        binary=ROOT/".local/variants/closure-certified-01a1fb7c"/("abc.exe" if os.name=="nt" else "abc")
        h=sha256(binary.read_bytes()).hexdigest()
        m=dict(kind=args.kind,binary_sha256=dict.fromkeys("35",h),cpus=list(args.cpus),rows=rows)
        if args.action=="plan":
            write_once(manifest,(json.dumps(m,indent=2)+"\n").encode())
            print(" ".join(r["truth"] for r in rows))
            return
        assert json.loads(manifest.read_bytes())==m
        args.work.mkdir(parents=True,exist_ok=True)
        with ThreadPoolExecutor(max_workers=len(args.cpus)) as pool:
            jobs=[pool.submit(run_lane,[r for r in rows if r["cpu"]==c],args,m["binary_sha256"]) for c in args.cpus]
            for job in jobs: job.result()
        print("Verified",2*len(rows),"timed rows",flush=True)
    else:
        m=json.loads(manifest.read_bytes())
        assert m["rows"]==rows and m["cpus"]==list(args.cpus) and m["kind"]==args.kind
        summary=export_or_check(args,m,history,exact)
        print(json.dumps({k:summary[k] for k in ("functions","runs","totals","common","gm","gained","lost")}))


if __name__=="__main__":
    main()
