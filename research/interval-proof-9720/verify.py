"""Replay exported circuits and recompute the frozen and independent study results."""
import argparse
import hashlib
import json
from math import exp, isclose, log
from pathlib import Path
from statistics import mean
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"tools"))
from audit_batch import audit
from witness import simulate


def verify(final):
    restored = HERE/".local/final-reproduction"
    restored.mkdir(parents=True,exist_ok=True)
    with ZipFile(HERE/"final-reproduction.zip") as z:
        for entry in z.namelist():
            dest = (restored/entry).resolve()
            assert dest.is_relative_to(restored.resolve())
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(z.read(entry))
    initial = {}
    known = {}
    for kind in ("main","ablation"):
        source=restored/("evidence/e14-"+kind)
        result=audit(source)
        assert result==json.loads((source/"audit.json").read_text())
        initial[kind]={k:v for k,v in result.items() if k!="comparisons"}
        if kind=="main":
            for file in source.glob("*.jsonl"):
                for line in file.read_bytes().splitlines():
                    row=json.loads(line)
                    if "witness" in row:
                        w=row["witness"]
                        assert known.setdefault(w["truth"],w["activity"])==w["activity"]
    plan=json.loads((HERE/"evidence/confirmation-plan.json").read_text())
    designs={"pilot-0189":("0189","ABBA",20,30),"pilot-001e":("001e","BAAB",24,30),
             "saved-pair-0189":("0189","BCCB",20,30),"saved-pair-001e":("001e","CBBC",24,30),
             "ablation-0189":("0189","ODHBBHDO",20,30),"hard-018b":("018b","BA",28,300),
             "hard-saved-018b":("018b","C",28,300)}
    if final:
        designs.update({"confirmation-"+x["truth"]:(x["truth"],x["order"],x["cpu"],plan["cap"])
                        for x in plan["cases"]})
    hashes={}
    results={}
    panel={"A":{},"C":{}}
    for name,(truth,order,cpu,cap) in designs.items():
        path=HERE/"evidence"/(name+".jsonl")
        if not final and not path.exists():
            continue
        rows=[json.loads(x) for x in path.read_bytes().splitlines()]
        if not final and len(rows)<len(order):
            continue
        assert len(rows)==len(order)
        observations=[]
        for i,(row,arm) in enumerate(zip(rows,order),1):
            assert row["command"][1:]==["-c",f"pexact -I 4 -M 2 {truth}"]
            assert row["timeout_s"]==cap and row["child_affinity"]==[cpu]
            assert row["experiment"]["arm"]==arm and row["experiment"]["order"]==i
            assert row["experiment"]["truth"]==truth and row["experiment"]["cpu"]==cpu
            role=arm if arm in "AC" else "B"
            assert hashes.setdefault(role,row["binary_sha256"])==row["binary_sha256"]
            raw=row["solver_output"]
            assert hashlib.sha256(raw.encode()).hexdigest()==row["solver_log_sha256"]
            wall=row["wall_s"]
            assert 0<wall<=cap+3 and isclose(row["capped_wall_s"],min(wall,cap))
            if row["status"]=="timeout":
                assert wall>=cap-0.05 and "witness" not in row
                w=None
            else:
                assert row["status"]=="solver_completed_verified_witness" and row["returncode"]==0
                w=simulate(raw,4,int(truth,16))
                assert w==row["witness"]
                assert known.setdefault(truth,w["activity"])==w["activity"]
            obs=dict(arm=arm,wall_s=wall,capped_s=min(wall,cap),activity=w and w["activity"])
            observations.append(obs)
            if name.startswith("confirmation-"):
                panel[arm][truth]=obs
        results[name]=observations
    out=dict(frozen=initial,binary_sha256=hashes,runs=results)
    if final:
        per={}
        for arm,group in panel.items():
            assert len(group)==len(plan["cases"])
            per[arm]=dict(completed=sum(x["activity"] is not None for x in group.values()),
                          capped_s=sum(x["capped_s"] for x in group.values()))
        ratios={t:panel["A"][t]["wall_s"]/c["wall_s"] for t,c in panel["C"].items()
                if c["activity"] is not None and panel["A"][t]["activity"] is not None}
        out["confirmation"]=dict(total=len(plan["cases"]),methods=per,common=len(ratios),
            paired_gm=exp(mean(log(r) for r in ratios.values())) if ratios else None,
            ratios=ratios,slower=[t for t,r in ratios.items() if r<1],
            gained=[t for t,c in panel["C"].items() if c["activity"] is not None and panel["A"][t]["activity"] is None],
            lost=[t for t,c in panel["C"].items() if c["activity"] is None and panel["A"][t]["activity"] is not None])
    return out


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--final",action="store_true")
    print(json.dumps(verify(p.parse_args().final),indent=2))
