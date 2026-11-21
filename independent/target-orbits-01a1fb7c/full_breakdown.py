"""Read the paired export and quantify where the first-gate rule changes outcomes."""
import argparse
from bisect import bisect_left, bisect_right
from datetime import datetime
import json
from pathlib import Path

from audit_pairs import HERE, audit, historical


def breakdown(root,recovery_records=None,occupancy=None):
    manifest=json.loads((root/"manifest.json").read_bytes())
    rows=[json.loads(s) for s in (root/"runs.jsonl").read_text().splitlines()]
    family=json.loads((HERE/"orbit-check.json").read_bytes())["family"]
    assert [c["truth"] for c in manifest]==list(family) and len(manifest)==208
    historical_values=historical()
    def summarize(subset):
        selected=[c for c in manifest if c["truth"] in subset]
        observations=[r for r in rows if r["experiment"]["truth"] in subset]
        result=audit(selected,observations,historical_values)
        return {k:v for k,v in result.items() if k not in ("binary_sha256","ratios","verified_resimulations")}
    groups={"no_first_gate_removed":[],"permutation_reaches_signed_count":[],"phase_removes_more":[]}
    for t,g in family.items():
        assert 1<=g["signed"]<=g["plain"]<=30
        if g["signed"]==30:
            label="no_first_gate_removed"
        elif g["signed"]==g["plain"]:
            label="permutation_reaches_signed_count"
        else:
            label="phase_removes_more"
        groups[label].append(t)
    report={name:summarize(set(ts)) for name,ts in groups.items()}
    if recovery_records:
        crossed=set()
        events={}
        for path in recovery_records:
            recovery=json.loads(path.read_bytes())
            cutoff=datetime.fromisoformat(recovery["restart_first_request_utc"])
            before=[r for r in rows if datetime.fromisoformat(r["start_utc"])<cutoff]
            assert len(before)==sum(recovery["retained"].values())
            for status,count in recovery["retained"].items():
                assert sum(r["status"]==status for r in before)==count
            earlier={(r["experiment"]["truth"],r["experiment"]["arm"]) for r in before}
            split={t for t in family if ((t,"A") in earlier)!=((t,"B") in earlier)}
            events[cutoff.isoformat()]=sorted(split)
            crossed.update(split)
        report["cross_interruption_functions"]=events
        report["same_session_pairs"]=summarize(set(family)-crossed)
    if occupancy:
        samples=[json.loads(s) for s in occupancy.read_text(encoding="utf-8-sig").splitlines()]
        stamps=[datetime.fromisoformat(s["utc"].replace("Z","+00:00")).timestamp() for s in samples]
        assert stamps==sorted(set(stamps)) and stamps
        seen={core for s in samples for core in s["other_single_core"]}
        by_truth={t:[] for t in family}
        for r in rows:
            by_truth[r["experiment"]["truth"]].append(r)
        def fixed_other_count(r):
            start=datetime.fromisoformat(r["start_utc"]).timestamp()
            left=bisect_right(stamps,start)-1
            right=bisect_left(stamps,start+r["wall_s"])
            if left<0 or right>=len(samples):
                return None
            core=r["experiment"]["cpu"]
            window=samples[left:right+1]
            if any(stamps[i+1]-stamps[i]>45 for i in range(left,right)):
                return None
            if any(s["other_multicore_intersecting"] for s in window):
                return None
            counts={s["other_single_core"].count(core) for s in window}
            return counts.pop() if len(counts)==1 else None
        stable={}
        for t,rs in by_truth.items():
            left_count,right_count=map(fixed_other_count,rs)
            if left_count is not None and left_count==right_count:
                stable[t]=left_count
        report["host_sampling"]=dict(
            observations=len(samples),start_utc=samples[0]["utc"],end_utc=samples[-1]["utc"],
            cores_seen_with_other_pinned_abc=sorted(seen),
            observations_with_multicore_abc=sum(s["other_multicore_intersecting"]>0 for s in samples),
            excluding_cores_seen_shared=summarize({c["truth"] for c in manifest if c["cpu"] not in seen}),
            both_runs_bracketed_without_observed_abc_overlap=summarize({t for t,n in stable.items() if n==0}),
            both_runs_with_same_constant_observed_count=summarize(set(stable)),
            stable_counts_by_function=stable)
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("data",type=Path)
    p.add_argument("--pause-record",type=Path,action="append",help="repeat for each recorded restart")
    p.add_argument("--occupancy",type=Path)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    report=json.dumps(breakdown(args.data,args.pause_record,args.occupancy),indent=2)
    if args.output:
        args.output.write_text(report+"\n",encoding="utf-8")
    print(report)
