"""Recheck the published evidence from a clean checkout without running the timed benchmark again."""
import argparse
from bisect import bisect_right
from collections import Counter
from hashlib import sha256
import json
from math import exp, fsum, log
from pathlib import Path

from audit_cost_order import validate as validate_cost_search
from audit_family import COMPLETED, METHODS, audit as audit_family
from audit_library_domain import audit as audit_domain
from audit_reproduction import run as audit_original, source_check
from audit_results import audit as audit_candidates
from library import HERE, check
from native_audit import verify_archive


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit_sessions(folder):
    """Exclude cross-pause targets in a sensitivity check with the same three arms."""
    rows={}
    for path in sorted(folder.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            run=json.loads(line)
            key=(run["experiment"]["truth"],run["experiment"]["mode"])
            assert key not in rows
            rows[key]=run
    plan=read(folder/"manifest.json")
    assert len(rows)==len(plan["cases"])*len(METHODS)
    boundaries=[]
    interruptions=0
    for filename in ("pause-20261121.json","pause-20261121-second.json"):
        pause=read(folder/filename)
        retried=set()
        for old in pause["interrupted"]:
            key=(old["experiment"]["truth"],old["experiment"]["mode"])
            assert key not in retried
            retried.add(key)
            new=rows[key]
            assert old["status"]=="user_pause_no_completed_timing" and old["log_bytes"]==0
            assert old["solver_log_sha256"]==sha256(b"").hexdigest() and old["start_utc"]<new["start_utc"]
            for field in ("experiment","binary_sha256","command","timeout_s","child_affinity"):
                assert new[field]==old[field]
        cutoff=min(rows[key]["start_utc"] for key in retried)
        before=[run for run in rows.values() if run["start_utc"]<cutoff]
        states=Counter(run["status"] for run in before)
        assert len(before)==pause["completed_before_pause"]
        assert states[COMPLETED]==pause["witnesses_before_pause"] and states["timeout"]==pause["timeouts_before_pause"]
        boundaries.append(cutoff)
        interruptions+=len(retried)
    assert boundaries==sorted(boundaries)
    kept=[]
    split=[]
    for truth in plan["cases"]:
        periods={bisect_right(boundaries,rows[truth,m]["start_utc"]) for m in METHODS}
        (kept if len(periods)==1 else split).append(truth)
    comparisons={}
    for control in METHODS[:-1]:
        ratios=[]
        gained=lost=0
        for truth in kept:
            left,right=rows[truth,control],rows[truth,METHODS[-1]]
            if left["status"]==right["status"]==COMPLETED:
                ratios.append(left["wall_s"]/right["wall_s"])
            elif left["status"]!=right["status"]:
                if right["status"]==COMPLETED: gained+=1
                else: lost+=1
        comparisons[control]=dict(common=len(ratios),paired_gm=exp(fsum(map(log,ratios))/len(ratios)) if ratios else None,
                                  gained=gained,lost=lost)
    return dict(resume_utc=boundaries,interrupted_launches=interruptions,within_session_targets=len(kept),
                split_targets=split,comparisons=comparisons)


def verify(sources=None):
    evidence=HERE/"evidence"
    original=audit_original()
    archived=read(evidence/"reproduction-reaudit.json")
    assert original == {k:v for k,v in archived.items() if k!="sources"}
    if sources:
        assert source_check(sources)==archived["sources"]
    candidates=audit_candidates()
    assert candidates==read(evidence/"research-audit.json")
    complete=read(evidence/"leaves-690.json")
    assert check(complete,read(evidence/"leaves-660.json"))==complete["verified"]==208
    cost_search=read(evidence/"cost-order-662.json")
    assert validate_cost_search(cost_search)==cost_search["audit"]
    assert cost_search["audit"]["exact_within_cap"]==208
    coverage=audit_domain(complete)
    assert coverage==read(evidence/"library-domain.json")
    verify_archive(complete["circuits"],evidence/"native-library")
    main=audit_family(evidence/"family-main",True,complete)
    assert main==read(evidence/"family-main/audit.json")
    assert main["independent_library_matches"]==main["verified_witnesses"]
    sessions=audit_sessions(evidence/"family-main")
    return dict(original=original["groups"],candidates=candidates["timed_runs"],
                exact_library_classes=complete["verified"],covered_truth_tables=coverage["distinct_truth_tables"],
                independent_cost_search=cost_search["audit"],final_runs=main["checked_runs"],
                final_witnesses=main["verified_witnesses"],sessions=sessions,source_archives_checked=bool(sources))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--sources",type=Path,help="Also check pinned upstream archives and prepared source files")
    args=parser.parse_args()
    print(json.dumps(verify(args.sources),indent=2))
