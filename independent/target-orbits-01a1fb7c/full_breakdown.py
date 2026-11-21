"""Read the paired export and quantify where the first-gate rule changes outcomes."""
import argparse
from datetime import datetime
import json
from pathlib import Path

from audit_pairs import HERE, audit, historical


def breakdown(root,pause_record=None):
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
    if pause_record:
        recovery=json.loads(pause_record.read_bytes())
        cutoff=datetime.fromisoformat(recovery["restart_first_request_utc"])
        before=[r for r in rows if datetime.fromisoformat(r["start_utc"])<cutoff]
        assert len(before)==sum(recovery["retained"].values())
        for status,count in recovery["retained"].items():
            assert sum(r["status"]==status for r in before)==count
        earlier={(r["experiment"]["truth"],r["experiment"]["arm"]) for r in before}
        crossed={t for t in family if ((t,"A") in earlier)!=((t,"B") in earlier)}
        report["cross_pause_functions"]=sorted(crossed)
        report["same_session_pairs"]=summarize(set(family)-crossed)
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("data",type=Path)
    p.add_argument("--pause-record",type=Path)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    report=json.dumps(breakdown(args.data,args.pause_record),indent=2)
    if args.output:
        args.output.write_text(report+"\n",encoding="utf-8")
    print(report)
