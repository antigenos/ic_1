"""Recompute paired outcomes, raw evidence hashes and witness values."""
import argparse
from hashlib import sha256
import json
from math import exp, log
from pathlib import Path
from statistics import mean
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"tools"))
from witness import simulate


def audit(manifest, rows, expected):
    by_case={}
    hashes={}
    for row in rows:
        meta=row["experiment"]
        t,arm=meta["truth"],meta["arm"]
        assert (t,arm) not in by_case and arm in "AB"
        assert row["binary_sha256"] == hashes.setdefault(arm,row["binary_sha256"])
        assert row["child_affinity"]==[meta["cpu"]]
        assert row["wall_s"]<=row["timeout_s"]+3
        assert abs(row["capped_wall_s"]-min(row["wall_s"],row["timeout_s"]))<1e-6
        raw=row["solver_output"].encode()
        assert sha256(raw).hexdigest()==row["solver_log_sha256"]
        if row["status"]=="solver_completed_verified_witness":
            assert row["returncode"]==0
            witness=simulate(raw.decode(),4,int(t,16))
            assert witness==row["witness"] and (t not in expected or witness["activity"]==expected[t])
        else:
            assert row["status"]=="timeout" and row["wall_s"]>=row["timeout_s"]-0.15
        by_case[t,arm]=row
    by_arm={a:{"completed":0,"capped_s":0.0} for a in "AB"}
    ratios={}
    only={a:[] for a in "AB"}
    assert len(by_case)==2*len(manifest)
    for case in manifest:
        t=case["truth"]
        a,b=(by_case[t,key] for key in "AB")
        for arm,row in (("A",a),("B",b)):
            assert row["experiment"]["cpu"]==case["cpu"]
            assert row["experiment"]["order"]==1+case["order"].index(arm)
            by_arm[arm]["completed"]+=int("witness" in row)
            by_arm[arm]["capped_s"]+=row["capped_wall_s"]
        if "witness" in a and "witness" in b:
            assert a["witness"]["activity"]==b["witness"]["activity"]
            ratios[t]=a["wall_s"]/b["wall_s"]
        elif "witness" in a or "witness" in b:
            only["A" if "witness" in a else "B"].append(t)
    return dict(cases=len(manifest),arms=by_arm,common=len(ratios),
                paired_geomean=exp(mean(map(log,ratios.values()))) if ratios else None,
                only=only,ratios=ratios,slower=[t for t,v in ratios.items() if v<1],
                verified_resimulations=sum(d["completed"] for d in by_arm.values()),binary_sha256=hashes)


def historical():
    costs={}
    for arm in ("both","author","support"):
        path=HERE/f"reproduction/evidence/e14-main/{arm}.jsonl"
        for line in path.read_text().splitlines():
            row=json.loads(line)
            if "witness" in row:
                t=row["experiment"]["truth"]
                assert costs.setdefault(t,row["witness"]["activity"])==row["witness"]["activity"]
    return costs


def read_raw(root):
    rows=[]
    for path in sorted(root.glob("*/*/result.json")):
        row=json.loads(path.read_text())
        raw=path.with_name("solver.log").read_bytes()
        row.update(solver_output=raw.decode(),solver_log_sha256=sha256(raw).hexdigest())
        rows.append(row)
    return rows


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("dir",type=Path)
    p.add_argument("--export",type=Path)
    args=p.parse_args()
    manifest=json.loads((args.dir/"manifest.json").read_text())
    recorded=args.dir/"runs.jsonl"
    rows=([json.loads(s) for s in recorded.read_text().splitlines()] if recorded.exists()
          else read_raw(args.dir))
    report=audit(manifest,rows,historical())
    if args.export:
        args.export.mkdir(parents=True,exist_ok=False)
        (args.export/"manifest.json").write_bytes((args.dir/"manifest.json").read_bytes())
        (args.export/"runs.jsonl").write_bytes(("".join(json.dumps(r,separators=(",",":"))+"\n" for r in rows)).encode())
        (args.export/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
