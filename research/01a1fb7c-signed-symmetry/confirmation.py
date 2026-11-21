"""Build a predeclared disjoint sample, run equal-cap lanes and audit their public logs."""
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

OUT=HERE/"confirmation"
MANIFEST=OUT/"manifest.json"


def plan(lanes=(4,6,8,10,12,14,16,18)):
    old=json.loads((HERE/"order-validation.json").read_text())["cohort"]
    excluded={"0189","07b4",*(r["truth"] for r in old)}
    cells={}
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        for line in z.read("evidence/e14-main/both.jsonl").splitlines():
            r=json.loads(line)
            t=r["experiment"]["truth"]
            if t in excluded: continue
            v=int(t,16)
            difficult="timeout" if r["status"]=="timeout" else ("fast" if r["wall_s"]<=10 else "medium")
            benefit=len(leaders(v,True))<len(leaders(v,False))
            cells.setdefault((difficult,benefit),[]).append(t)
    # Allocate all four timeout cases separate lanes so that one lane does not carry both.
    rows=[]
    for cell in sorted(cells,key=lambda c:(("timeout","medium","fast").index(c[0]),c[1])):
        ordered=sorted(cells[cell],key=lambda t:sha256(("01a1fb7c-confirm-v1:"+t).encode()).digest())
        for t in ordered[:2]:
            i=len(rows)
            order=("FQNH","QHFN","HNQF","NFHQ")[i%4]
            rows.append(dict(truth=t,cpu=lanes[i%len(lanes)],order=order,seconds=300,
                             difficulty=cell[0],signed_stricter=cell[1],cell_size=len(ordered)))
    assert len(rows)==12 and not excluded.intersection(r["truth"] for r in rows)
    return rows


def run_lane(records,prepared,directory,resume_id):
    for r in records:
        t=r["truth"]
        path=directory/f"confirm-{t}.jsonl"
        if path.exists() and not resume_id:
            # A partial attempt is preserved for process inspection rather than duplicated.
            replay(path,t,r["order"],r["cpu"],r["seconds"])
            continue
        options=["--resume-id",resume_id] if resume_id else []
        if directory.resolve() != OUT.resolve():
            options.extend(["--raw-root",str(directory/"raw")])
        subprocess.run([sys.executable,str(HERE/"compare.py"),t,r["order"],str(path),"--cpu",str(r["cpu"]),
                        "--cap",str(r["seconds"]),"--prepared",str(prepared),*options],check=True)


def outcomes(data):
    result={"functions":len(data),"runs":4*len(data),"totals":{},"relative_to_N":{}}
    for key in "FQHN":
        rows=[case[key] for case in data.values()]
        assert len({r["binary_sha256"] for r in rows})==1
        result["totals"][key]=dict(solved=sum("witness" in r for r in rows),capped_s=fsum(r["capped_wall_s"] for r in rows))
        if key=="N": continue
        ratios={t:v[key]["wall_s"]/v["N"]["wall_s"] for t,v in data.items() if all("witness" in v[k] for k in (key,"N"))}
        result["relative_to_N"][key]=dict(ratios=ratios,common=len(ratios),gm=exp(fsum(map(log,ratios.values()))/len(ratios)) if ratios else None,
            gained=[t for t,v in data.items() if "witness" in v["N"] and "witness" not in v[key]],
            lost=[t for t,v in data.items() if "witness" not in v["N"] and "witness" in v[key]])
    return result


def report(manifest,directory=OUT):
    data={}
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        archived={}
        for method in ("author","support","both"):
            for line in z.read(f"evidence/e14-main/{method}.jsonl").splitlines():
                old=json.loads(line)
                if "witness" in old:
                    archived.setdefault(old["experiment"]["truth"],set()).add(old["witness"]["activity"])
    by_case={}
    for r in manifest:
        t=r["truth"]
        rows=replay(directory/f"confirm-{t}.jsonl",t,r["order"],r["cpu"],r["seconds"])
        data[t]={row["experiment"]["arm"]:row for row in rows}
        values={row["witness"]["activity"] for row in rows if "witness" in row}
        assert len(values|archived.get(t,set()))<=1
        assert len({data[t][arm]["binary_sha256"] for arm in "QHN"})==1
        by_case[t]={arm:{"status":row["status"],"wall_s":row["wall_s"],
                        "activity":row.get("witness",{}).get("activity")} for arm,row in data[t].items()}
    result=outcomes(data)
    result["cases"]=by_case
    result["by_signed_exclusion"]={}
    for strict in (False,True):
        group={r["truth"]:data[r["truth"]] for r in manifest if r["signed_stricter"]==strict}
        result["by_signed_exclusion"]["strict" if strict else "identical"]=outcomes(group)
    recovery=directory/"pause-recovery.json"
    if recovery.exists():
        old=json.loads(recovery.read_text())
        first_epoch=old["completed_before_pause"]
        for t,arms in first_epoch.items():
            for arm,digest in arms.items():
                assert data[t][arm]["solver_log_sha256"]==digest
        result["all_four_after_resume"]=outcomes({t:v for t,v in data.items() if t not in first_epoch})
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("plan","run","report"))
    p.add_argument("--prepared",type=Path,default=HERE.parents[1])
    p.add_argument("--directory",type=Path,default=OUT)
    p.add_argument("--cpus",type=int,nargs="+",default=(4,6,8,10,12,14,16,18))
    p.add_argument("--resume-id")
    args=p.parse_args()
    if len(set(args.cpus))!=len(args.cpus) or min(args.cpus)<0:
        p.error("Supply distinct nonnegative logical CPUs")
    manifest=plan(tuple(args.cpus))
    destination=args.directory/"manifest.json"
    if args.action=="plan":
        args.directory.mkdir(parents=True,exist_ok=True)
        if destination.exists():
            assert json.loads(destination.read_text())==manifest
        else:
            destination.write_text(json.dumps(manifest,indent=2)+"\n")
        print(" ".join(r["truth"] for r in manifest))
    else:
        assert json.loads(destination.read_text())==manifest
        if args.action=="run":
            cpus=sorted({r["cpu"] for r in manifest})
            with ThreadPoolExecutor(max_workers=len(cpus)) as pool:
                jobs=[pool.submit(run_lane,[r for r in manifest if r["cpu"]==cpu],args.prepared.resolve(),args.directory,args.resume_id) for cpu in cpus]
                for job in jobs: job.result()
        else:
            print(json.dumps(report(manifest,args.directory),indent=2))
