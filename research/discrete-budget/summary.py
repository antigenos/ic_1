"""Verify completed timing blocks against raw logs and summarize paired end-to-end cost."""
import argparse
from datetime import datetime
from collections import Counter,defaultdict
from itertools import combinations
import json
from math import exp,fsum,log
from pathlib import Path
import sys
from build import HERE,ROOT,gitfile
sys.path.insert(0,str(ROOT/"tools"))
from witness import simulate
from audit import read_querylog


def read_blocks(prefix):
    out,limits={},{}
    lower=json.loads(gitfile("evidence/family-bounds-432.json"))["lower_bounds"]
    for src in sorted((HERE/"results").glob(prefix+"-*")):
        if not src.is_dir() or not (src/"complete.json").exists():
            continue
        plan=json.loads((src/"manifest.json").read_text())
        assert len(plan["cases"])==1 and plan["kind"] in ("three","four","holdout")
        truth=plan["cases"][0]
        assert truth not in out
        groups=defaultdict(list)
        guard=[json.loads(l) for l in (src/"guard.jsonl").read_text().splitlines()]
        assert all(not x["foreign"] and x["physical"]==plan["physical"] for x in guard)
        assert plan["env"]==dict(OPTWIN_MODE="both",REPLAY_RULES="both",REPLAY_BUDGET="1")
        rows=[]
        for dest in src.iterdir():
            if not dest.is_dir():
                continue
            row=json.loads((dest/"result.json").read_text())
            m=row["experiment"]["method"]
            start=datetime.fromisoformat(row["start_utc"]).timestamp()
            assert guard[0]["t"] <= start and guard[-1]["t"]>=start+row["wall_s"]-.02
            assert row["binary_sha256"]==plan["binaries"][m]
            assert row["child_affinity"]==[plan["cpu"]] and row["timeout_s"]==plan["cap"]
            assert row["command"]==["abc.exe","-c","pexact -I 4 -M 2 "+truth]
            if row["status"]=="solver_completed_verified_witness":
                replay=simulate((dest/"solver.log").read_text(),4,int(truth,16))
                assert replay==row["witness"] and replay["activity"]==lower[truth] and row["returncode"]==0
            else:
                assert row["status"]=="timeout" and row["capped_wall_s"]==plan["cap"]
            rows.append(row)
        rows.sort(key=lambda r:r["experiment"]["order"])
        methods=[r["experiment"]["method"] for r in rows]
        assert len(rows)==2*len(plan["methods"]) and methods==methods[::-1] and set(methods)==set(plan["methods"])
        for row in rows:
            groups[row["experiment"]["method"]].append(row)
        out[truth]=groups
        limits[truth]=dict(cpu=plan["cpu"],physical=plan["physical"],source=plan["source_commit"],folder=src.name,
                           observed_max_gap=json.loads((src/"complete.json").read_text())["max_sample_gap"])
    return out,limits


def summarize(prefix):
    data,manifest=read_blocks(prefix)
    if not data:
        raise ValueError("No accepted complete measured blocks for "+prefix)
    methods=list(next(iter(data.values())))
    agg={}
    for m in methods:
        groups=[arms[m] for arms in data.values()]
        rows=[r for group in groups for r in group]
        done=lambda r:r["status"]=="solver_completed_verified_witness"
        agg[m]=dict(functions_both_orders=sum(all(map(done,g)) for g in groups),functions=len(groups),
                    completed_runs=sum(map(done,rows)),runs=len(rows),capped_s=fsum(r["capped_wall_s"] for r in rows))
    pairs={}
    for a,b in combinations(("joint","interval","holes","trigger"),2):
        if a not in methods or b not in methods:
            continue
        paired=[]
        individual={}
        for truth,arms in data.items():
            values=[]
            for first,second in zip(arms[a],arms[b]):
                good=all(r["status"]=="solver_completed_verified_witness" for r in (first,second))
                values.append([first["wall_s"],second["wall_s"]] if good else None)
                if good:
                    paired.append(values[-1])
            individual[truth]=values
        pairs[a+"/"+b]=dict(common_pairs=len(paired),common_function_both_orders=sum(all(v) for v in individual.values()),
            first_s=fsum(v[0] for v in paired),second_s=fsum(v[1] for v in paired),
            gm=exp(fsum(log(x/y) for x,y in paired)/len(paired)) if paired else None,
            both_orders_faster=[t for t,v in individual.items() if all(row and row[0]>row[1] for row in v)],
            per_order_wall_seconds=individual)
    return dict(blocks=manifest,methods=agg,pairs=pairs)


def diagnostic(prefix):
    from audit import assess
    result={}
    for folder in sorted((HERE/"results").glob(prefix+"-*")):
        if not folder.is_dir() or not (folder/"complete.json").exists():
            continue
        plan=json.loads((folder/"manifest.json").read_text())
        for dest in sorted(folder.glob("*-*-*")):
            if not dest.is_dir():
                continue
            truth,_,method=dest.name.split("-")
            key=truth+"-"+method
            assert key not in result
            path=dest/("solver.log.gz" if (dest/"solver.log.gz").exists() else "solver.log")
            data=assess(path,method)
            seq=[{k:v for k,v in (field.split("=") for field in l.split()[1:]) if k!="seconds"}
                 for l in read_querylog(path) if l.startswith("WINDOW ")]
            # Independently check the emitted outer skips against integer domains and
            # only previously answered UNSAT on the same charged gate count.
            definitions={"__name__":"outer_audit"}
            exec(compile(gitfile("audit_windows.py"),"pinned_outer_audit.py","exec"),definitions)
            score=definitions["scores"]
            eliminated=defaultdict(set)
            reasons=Counter()
            for e in seq:
                r,lo,hi=map(int,[e["r"],e["lo"],e["hi"]])
                window=set(range(lo,hi+1))
                feasible=score(4,r)&window
                remaining=feasible-eliminated[r]
                if e["state"]=="skip":
                    assert not remaining
                    reasons["no_initial_score" if not feasible else "earlier_unsat"]+=1
                else:
                    assert remaining
                if e["state"]=="-1":
                    eliminated[r].update(window)
            result[key]=dict(**data,outer_skip_proof=reasons,outer_sequence=seq)
    assert result
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("prefix")
    p.add_argument("--diagnostic",action="store_true")
    args=p.parse_args()
    print(json.dumps((diagnostic if args.diagnostic else summarize)(args.prefix),indent=2))
