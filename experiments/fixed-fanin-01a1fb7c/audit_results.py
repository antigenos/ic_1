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
from lower_bound import cheaper_circuit


def read_case(group, planned, cap):
    brief=json.loads((group/"summary.json").read_text())
    assert [s["mode"] for s in brief]==planned, group
    actual_dirs={p.name for p in group.iterdir() if p.is_dir()}
    assert actual_dirs=={f"{i:02}-{mode}" for i,mode in enumerate(planned,1)}, group
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
        assert result["timeout_s"]==cap and 0<s["wall_s"]<=cap+3
        assert result["capped_wall_s"]==s["capped_s"]
        assert t==group.name.split("-")[1]
        log_bytes=(run/"solver.log").read_bytes().replace(b"\r\n",b"\n")
        if result["status"]=="solver_completed_verified_witness":
            assert result["returncode"]==0 and b"Total runtime" in log_bytes
            check=simulate(log_bytes.decode(),4,int(t,16))
            assert check==result["witness"] and check["activity"]==s["activity"]
        else:
            assert result["status"]=="timeout" and s["activity"] is None and s["wall_s"]>=cap
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
    plan={
        "timing-0189": ("base ops margins all all margins ops base",60),
        "timing-0369": ("base all",60),
        "timing-0369-long": ("all base",300),
    }
    for case in ("0019","0189"):
        plan["interval-"+case]=("base interval interval base",60)
        plan["types-"+case]=("base types-only types types types-only base",60)
        plan["partition-"+case]=("base split-bit split-five split-five split-bit base",60)
        plan["cofactor-"+case]=("base cofactor-whole cofactor cofactor cofactor-whole base",60)
        plan["prefix-"+case]=("base seed-cofactor seed-prefix2 seed-prefix2 seed-cofactor base",60)
        plan["bounded-"+case]=("base bounded-plain bounded-projected bounded-projected bounded-plain base",60)
    for case,cap in (("0189",60),("0198",180)):
        plan["xor-"+case]=("base xor-only xor-proof xor-proof xor-only base",cap)
    groups={}
    for path in sorted((HERE/"evidence").glob("*/summary.json")):
        name=path.parent.name
        if name not in plan and name.startswith("holdout-"):
            continue
        order,cap=plan[name]
        groups[name]=read_case(path.parent,order.split(),cap)
    assert groups.keys()==plan.keys()
    optima={"0189":304}
    for case in ("0019","0198"):
        proof=json.loads((HERE/"evidence"/("proof-"+case+".json")).read_text())
        assert proof["truth"]==case and proof["cheaper_exists"] is False
        assert cheaper_circuit(4,int(case,16),proof["strict_upper"])==(False,proof["states"])
        optima[case]=proof["strict_upper"]
    for group in groups.values():
        for row in group["rows"]:
            if row["activity"] is not None and row["truth"] in optima:
                assert row["activity"]==optima[row["truth"]]
    counts=sum(len(v["rows"]) for v in groups.values())
    witnesses=sum(r["activity"] is not None for v in groups.values() for r in v["rows"])
    return dict(timed_runs=counts,replayed_witnesses=witnesses,strict_optima=optima,groups=groups)


if __name__=="__main__":
    out=audit()
    if len(sys.argv)>1:
        Path(sys.argv[1]).write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({k:v for k,v in out.items() if k!="groups"}))
