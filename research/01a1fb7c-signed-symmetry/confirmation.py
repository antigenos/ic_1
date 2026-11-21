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


def plan():
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
    lanes=(4,6,8,10,12,14,16,18)
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


def run_lane(records,prepared):
    for r in records:
        t=r["truth"]
        path=OUT/f"confirm-{t}.jsonl"
        if path.exists():
            # A partial attempt is preserved for process inspection rather than duplicated.
            replay(path,t,r["order"],r["cpu"],r["seconds"])
            continue
        subprocess.run([sys.executable,str(HERE/"compare.py"),t,r["order"],str(path),"--cpu",str(r["cpu"]),
                        "--cap",str(r["seconds"]),"--prepared",str(prepared)],check=True)


def report(manifest):
    data={}
    for r in manifest:
        t=r["truth"]
        rows=replay(OUT/f"confirm-{t}.jsonl",t,r["order"],r["cpu"],r["seconds"])
        data[t]={row["experiment"]["arm"]:row for row in rows}
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


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("plan","run","report"))
    p.add_argument("--prepared",type=Path,default=HERE.parents[1])
    args=p.parse_args()
    manifest=plan()
    if args.action=="plan":
        OUT.mkdir(exist_ok=True)
        if MANIFEST.exists():
            assert json.loads(MANIFEST.read_text())==manifest
        else:
            MANIFEST.write_text(json.dumps(manifest,indent=2)+"\n")
        print(" ".join(r["truth"] for r in manifest))
    else:
        assert json.loads(MANIFEST.read_text())==manifest
        if args.action=="run":
            cpus=sorted({r["cpu"] for r in manifest})
            with ThreadPoolExecutor(max_workers=len(cpus)) as pool:
                jobs=[pool.submit(run_lane,[r for r in manifest if r["cpu"]==cpu],args.prepared.resolve()) for cpu in cpus]
                for job in jobs: job.result()
        else:
            print(json.dumps(report(manifest),indent=2))
