"""Recheck each exported run and summarize only the registered paired cohorts."""
from hashlib import sha256
import json
from math import exp, fsum, log
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"tools"))
from witness import simulate


def replay(path,target,order,cpu,cap):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows)!=len(order):
        raise ValueError(f"Incomplete set: {path.name}")
    values = set()
    for i,(arm,row) in enumerate(zip(order,rows),1):
        assert row["experiment"]==dict(cpu=cpu,arm=arm,order=i,truth=target)
        assert row["command"]==["abc.exe","-c",f"pexact -I 4 -M 2 {target}"] or row["command"]==["abc","-c",f"pexact -I 4 -M 2 {target}"]
        assert row["child_affinity"]==[cpu] and row["timeout_s"]==cap
        assert 0<row["wall_s"]<=cap+3 and row["capped_wall_s"]==min(row["wall_s"],cap)
        text = row["solver_output"]
        assert sha256(text.encode()).hexdigest()==row["solver_log_sha256"]
        if row["status"]=="timeout":
            assert "witness" not in row
        else:
            assert row["returncode"]==0 and row["status"]=="solver_completed_verified_witness"
            w=simulate(text,4,int(target,16))
            assert w==row["witness"]
            values.add(w["activity"])
    assert len(values)<=1
    return rows


def main():
    validation=json.loads((HERE/"order-validation.json").read_text())
    bycase={}
    for idx,case in enumerate(validation["cohort"]):
        t=case["truth"]
        rs=replay(HERE/f"strata-{t}.jsonl",t,("FPJ","PJF","JFP")[idx%3],(4,6,8,10,12,16)[idx],300)
        bycase[t]={row["experiment"]["arm"]:row for row in rs}
    pilots={}
    for file,t,order,cpu,cap in (("pilot-0189","0189","FUSSUFO",14,60),
                                 ("ordered-0189","0189","PJJPK",14,60),("pilot-07b4","07b4","FS",18,300)):
        rs=replay(HERE/(file+".jsonl"),t,order,cpu,cap)
        pilots[file]=[dict(arm=row["experiment"]["arm"],wall_s=row["wall_s"],status=row["status"],
                           activity=row.get("witness",{}).get("activity")) for row in rs]
    totals={}
    for arm in "FPJ":
        rs=[r[arm] for r in bycase.values()]
        assert len({r["binary_sha256"] for r in rs})==1
        totals[arm]=dict(completed=sum("witness" in r for r in rs),capped_wall_s=fsum(r["capped_wall_s"] for r in rs))
    comparisons={}
    for arm in "FP":
        ratios={t:rs[arm]["wall_s"]/rs["J"]["wall_s"] for t,rs in bycase.items()
                if "witness" in rs[arm] and "witness" in rs["J"]}
        comparisons[arm]=dict(paired_ratios=ratios,geometric_mean=exp(fsum(map(log,ratios.values()))/len(ratios)) if ratios else None,
                              gained=[t for t,r in bycase.items() if "witness" not in r[arm] and "witness" in r["J"]],
                              lost=[t for t,r in bycase.items() if "witness" in r[arm] and "witness" not in r["J"]])
    return dict(strata_counts=totals,comparisons=comparisons,pilots=pilots,
                six_case_rows=sum(map(len,bycase.values())),verified_witnesses=sum(v["completed"] for v in totals.values()))


if __name__=="__main__":
    print(json.dumps(main(),indent=2))
