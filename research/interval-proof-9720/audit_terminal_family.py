"""Audit cold per-target bounded proofs and compare exact coverage to the frozen cohorts."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from math import fsum
from pathlib import Path
import subprocess
from zipfile import ZipFile

from terminal_compare import HERE, MODULES, PLAN, TERMINAL_REVISION, checked_answer, holdout_plan, terminal_family_plan


def read_panel(path, plan):
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    assert [(r["truth"],r["strict_cap"],r["arm"]) for r in rows] == plan
    assert [r["order"] for r in rows] == list(range(1,len(rows)+1))
    return rows


def audit(pilot, holdout, remaining=None):
    bounds = json.loads((HERE/"evidence/constructed-through-432.json").read_bytes())["bounds"]
    hashes = {}
    for name in MODULES:
        path = (HERE/name).relative_to(HERE.parents[1]).as_posix()
        blob = subprocess.check_output(["git","cat-file","blob",TERMINAL_REVISION+":"+path],cwd=HERE)
        hashes[name] = sha256(blob).hexdigest()
    hp = [(c["truth"],433,a) for c in holdout_plan(bounds)["cases"] for a in c["order"]]
    inputs = [(r,"pilot") for r in read_panel(pilot,PLAN) if r["strict_cap"]==433 and r["arm"]=="T"]
    inputs.extend((r,"holdout") for r in read_panel(holdout,hp) if r["arm"]=="T")
    if remaining is not None:
        inputs.extend((r,"new") for r in read_panel(remaining,terminal_family_plan(bounds,remaining=True)))
    assert len({r["truth"] for r,_ in inputs})==len(inputs)==(9 if remaining is None else 208)
    assert len({tuple(r["child_affinity"]) for r,_ in inputs}) == 1 and len(inputs[0][0]["child_affinity"])==1
    results = []
    for r,origin in sorted(inputs,key=lambda pair:pair[0]["truth"]):
        assert r["source_sha256"]==hashes and r["timeout_s"]==300 and r["arm"]=="T" and r["strict_cap"]==433
        seconds = min(r["wall_s"],300.)
        assert seconds>0
        witness = {}
        if r["status"]=="completed":
            proof=checked_answer(r,bounds)
            outcome=proof["status"]
            witness=proof.get("witness",{})
        else:
            assert r["status"]=="timeout" and r["wall_s"]>=299.95
            outcome="timeout"
        results.append(dict(truth=r["truth"],origin=origin,outcome=outcome,capped_elapsed_s=seconds,
                            budget_cost_s=seconds if witness else 300.,optimum=witness.get("activity",""),
                            gates=witness.get("gates","")))
    exact={r["truth"]:r["optimum"] for r in results if r["outcome"]=="independently_optimal"}
    summary=dict(trials=len(results),exact=len(exact),outcomes=Counter(r["outcome"] for r in results),
                 origins=Counter(r["origin"] for r in results),actual_capped_s=fsum(r["capped_elapsed_s"] for r in results),
                 charging_unresolved_300_s=fsum(r["budget_cost_s"] for r in results))
    if remaining is not None:
        summary["frozen_comparisons"]={}
        with ZipFile(HERE/"final-reproduction.zip") as z:
            for arm in ("author","support","both"):
                old=[json.loads(line) for line in z.read("evidence/e14-main/"+arm+".jsonl").splitlines()]
                assert {r["experiment"]["truth"] for r in old}=={r["truth"] for r in results}
                previously={r["experiment"]["truth"]:r["witness"]["activity"] for r in old if "witness" in r}
                common=exact.keys() & previously.keys()
                assert all(exact[t]==previously[t] for t in common)
                summary["frozen_comparisons"][arm]=dict(completed=len(previously),common=len(common),
                    gained=sorted(exact.keys()-previously.keys()),lost=sorted(previously.keys()-exact.keys()))
    return results,summary


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("pilot",type=Path)
    cli.add_argument("holdout",type=Path)
    cli.add_argument("--remaining",type=Path)
    cli.add_argument("--output",type=Path)
    args=cli.parse_args()
    if args.output and not args.remaining:
        cli.error("A final 208-row export requires the remaining panel")
    results,summary=audit(args.pilot,args.holdout,args.remaining)
    if args.output:
        with args.output.open("x",encoding="utf8",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(results[0]),lineterminator="\n")
            writer.writeheader()
            writer.writerows(results)
    print(json.dumps(summary,indent=2))
