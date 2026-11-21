"""Recompute per-case paired timings and replay every archived timed witness."""
import hashlib
import json
from math import exp, log
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from witness import simulate


def read_case(group):
    brief=json.loads((group/"summary.json").read_text())
    rows=[]
    for k,s in enumerate(brief,1):
        mode=s["mode"]
        run=group/f"{k:02}-{mode}"
        result=json.loads((run/"result.json").read_text())
        request=json.loads((run/"request.json").read_text())
        launch=json.loads((run/"launch.json").read_text())
        assert all(result[key]==v for key,v in request.items())
        assert result["child_affinity"]==launch["child_affinity"]==[result["experiment"]["cpu"]]
        assert result["pid"]==launch["pid"]
        t=result["experiment"]["truth"]
        assert result["command"][1:]==["-c",f"pexact -I 4 -M 2 {t}"]
        assert result["experiment"]["order"]==k and result["experiment"]["mode"]==mode
        assert (s["status"],s["wall_s"],s["capped_s"])==(
            result["status"],result["wall_s"],min(result["wall_s"],result["timeout_s"]))
        assert s["wall_s"]<=result["timeout_s"]+3
        log_bytes=(run/"solver.log").read_bytes()
        if result["status"]=="solver_completed_verified_witness":
            assert result["returncode"]==0
            check=simulate(log_bytes.decode(),4,int(t,16))
            assert check==result["witness"] and check["activity"]==s["activity"]
        else:
            assert result["status"]=="timeout" and s["activity"] is None
        rows.append(dict(**s,cpu=result["experiment"]["cpu"],truth=t,cap=result["timeout_s"],
                         binary=result["binary_sha256"],log_sha256=hashlib.sha256(log_bytes).hexdigest()))
    assert len({(r["truth"],r["cpu"],r["cap"]) for r in rows})==1
    assert len({r["activity"] for r in rows if r["activity"] is not None})<=1
    baseline=[r for r in rows if r["mode"]=="base"]
    summary={}
    for mode in dict.fromkeys(r["mode"] for r in rows):
        items=[r for r in rows if r["mode"]==mode]
        solved=[r for r in items if r["activity"] is not None]
        entry=dict(completed=len(solved),attempts=len(items),
                   capped_total_s=sum(r["capped_s"] for r in items),wall_s=[r["wall_s"] for r in items])
        if len(solved)==len(items)==len(baseline) and all(r["activity"] is not None for r in baseline):
            paired=[a["wall_s"]/b["wall_s"] for a,b in zip(baseline,items)]
            entry.update(paired_ratios=paired,paired_gm=exp(sum(log(x) for x in paired)/len(paired)))
        summary[mode]=entry
    return dict(rows=rows,methods=summary)


def audit():
    groups={}
    for path in sorted((HERE/"evidence").glob("*/summary.json")):
        groups[path.parent.name]=read_case(path.parent)
    counts=sum(len(v["rows"]) for v in groups.values())
    witnesses=sum(r["activity"] is not None for v in groups.values() for r in v["rows"])
    return dict(timed_runs=counts,replayed_witnesses=witnesses,groups=groups)


if __name__=="__main__":
    out=audit()
    if len(sys.argv)>1:
        Path(sys.argv[1]).write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({k:v for k,v in out.items() if k!="groups"}))
