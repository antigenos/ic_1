"""Deterministic stratified confirmation panel for the first-gate candidate."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from compare_orbits import HERE


def plan():
    source=HERE/"reproduction/evidence/e14-main/both.jsonl"
    strata=[[] for _ in range(4)]
    for line in source.read_text().splitlines():
        row=json.loads(line)
        t=row["experiment"]["truth"]
        if t in ("0189","0019","012d","6996"):
            continue
        level=3 if row["status"]=="timeout" else int(row["wall_s"]>=2)+int(row["wall_s"]>=30)
        strata[level].append(t)
    def key(t):
        return hashlib.sha256(("orbit-01a1fb7c-panel-v1/"+t).encode()).digest()
    groups=[sorted(group,key=key)[:4] for group in strata]
    return [dict(truth=t,stratum=h,cpu=16+2*((4*h+i)%8),order="AB" if (h+i)%2==0 else "BA")
            for h,g in enumerate(groups) for i,t in enumerate(g)]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",action="store_true")
    parser.add_argument("--directory",type=Path,default=HERE/"evidence/panel")
    a=parser.parse_args()
    cases=plan()
    if not a.run:
        print(json.dumps(cases,indent=2))
        return
    a.directory.mkdir(parents=True,exist_ok=False)
    (a.directory/"manifest.json").write_text(json.dumps(cases,indent=2)+"\n")
    def lane(cpu):
        for case in cases:
            if case["cpu"]==cpu:
                subprocess.run([sys.executable,str(HERE/"compare_orbits.py"),case["truth"],
                                str(a.directory/case["truth"]),"--order",case["order"],"--cap","60",
                                "--cpu",str(cpu)],check=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lane,sorted({c["cpu"] for c in cases})))


if __name__=="__main__":
    main()
