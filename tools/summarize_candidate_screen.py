"""Verify timed outputs and produce paired, same-batch screening measurements."""
from collections import defaultdict
import json
import math
from pathlib import Path
from statistics import mean
from witness import simulate

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/"evidence"


def check_result(directory,expected=None):
    row=json.loads((directory/"result.json").read_text())
    assert row["binary_sha256"]==json.loads((directory/"request.json").read_text())["binary_sha256"]
    assert row["child_affinity"]==[row["experiment"]["cpu"]]
    assert row["wall_s"]<=row["timeout_s"]+3
    truth=int(row["command"][2].split()[-1],16)
    if row["status"]=="solver_completed_verified_witness":
        assert simulate((directory/"solver.log").read_text(),4,truth)==row["witness"]
        if expected is not None:
            assert row["witness"]["activity"]==expected
    else:
        assert row["status"]=="timeout"
    return row


def summarize():
    official={r["experiment"]["truth"]:r["witness"]["activity"] for line in
              (E/"e14-main/both.jsonl").read_text().splitlines() if "witness" in (r:=json.loads(line))}
    batches={}
    total=0
    for summary in sorted(E.glob("screen-*/paired.json")):
        data=json.loads(summary.read_text())
        folder=summary.parent
        times=defaultdict(list)
        methods=[r["experiment"]["method"] for r in data]
        assert methods==list(reversed(methods)) and len(set(methods))*2==len(methods)
        for i,(method,rec) in enumerate(zip(methods,data),1):
            truth=rec["experiment"]["truth"]
            row=check_result(folder/f"{i:02d}-{method}",official[truth])
            assert row["wall_s"]==rec["wall_s"] and "witness" in row
            times[method].append(row["wall_s"])
            total+=1
        base=times["baseline"]
        batches[folder.name]={name:dict(seconds=t,mean_s=mean(t),
                                  paired_speedup=math.sqrt(base[0]*base[1]/(t[0]*t[1])),
                                  both_orders_faster=all(a>b for a,b in zip(base,t)))
                               for name,t in times.items()}
    hard={}
    for method,path in (("baseline","cofactor-e12-pair/018b-2-A"),
                        ("shared","screen-difficult-018b/1-C"),("prefix","screen-prefix-018b")):
        row=check_result(E/path,412)
        hard[method]={k:row[k] for k in ("wall_s","status","timeout_s","binary_sha256")}
        if "witness" in row: hard[method]["witness"]=row["witness"]
    return dict(verified_paired_runs=total,batches=batches,hard_018b=hard)


if __name__=="__main__":
    print(json.dumps(summarize(),indent=2))
