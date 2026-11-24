"""Describe completion, paired wall time and measurable gaps in a published census."""
import argparse
from datetime import datetime
from hashlib import sha256
import json
from math import exp, fsum, log
from pathlib import Path

from family import write_once


def compare(cases, baseline, candidate):
    a = {key: rows[baseline] for key, rows in cases.items()}
    b = {key: rows[candidate] for key, rows in cases.items()}
    common = [k for k in cases if "witness" in a[k] and "witness" in b[k]]
    ratios = {k:a[k]["wall_s"]/b[k]["wall_s"] for k in common}
    return dict(functions=len(cases), baseline_completed=sum("witness" in r for r in a.values()),
                candidate_completed=sum("witness" in r for r in b.values()),
                baseline_capped_s=fsum(r["capped_wall_s"] for r in a.values()),
                candidate_capped_s=fsum(r["capped_wall_s"] for r in b.values()),
                common=len(common), paired_gm=exp(fsum(map(log, ratios.values()))/len(common)) if common else None,
                gained=[k for k in cases if "witness" in b[k] and "witness" not in a[k]],
                lost=[k for k in cases if "witness" in a[k] and "witness" not in b[k]],
                slower_on_common={k:v for k,v in ratios.items() if v < 1})


def summarize(directory):
    manifest = json.loads((directory/"manifest.json").read_bytes())
    summary = json.loads((directory/"summary.json").read_bytes())
    stream = (directory/"runs.jsonl").read_bytes().replace(b"\r\n", b"\n")
    assert sha256(stream).hexdigest() == summary["raw_sha256"]
    by_target = {}
    for line in stream.splitlines():
        entry = json.loads(line)
        by_target.setdefault(entry["experiment"]["truth"],[]).append(entry)
    assert set(by_target) == {r["truth"] for r in manifest["rows"]}
    cases, gaps = {}, {}
    for config in manifest["rows"]:
        t = config["truth"]
        entries = by_target[t]
        assert "".join(e["experiment"]["arm"] for e in entries) == config["order"]
        cases[t] = {e["experiment"]["arm"]:e for e in entries}
        for prev, curr in zip(entries,entries[1:]):
            starts = (datetime.fromisoformat(curr["start_utc"])-datetime.fromisoformat(prev["start_utc"])).total_seconds()
            idle = starts-prev["wall_s"]
            if idle > 30:
                gaps.setdefault(t,[]).append(dict(after=prev["experiment"]["arm"],before=curr["experiment"]["arm"],gap_s=idle))
    arms = set(manifest["binary_sha256"])
    candidate = "5" if arms == {"3","5"} else "N"
    assert arms in ({"3","5"},{"F","H","N"})
    baselines = sorted(arms-{candidate})
    adjacent = {k:v for k,v in cases.items() if k not in gaps}
    return dict(raw_sha256=summary["raw_sha256"], candidate=candidate, inter_arm_gaps_over_30s=gaps,
                all_cases={a:compare(cases,a,candidate) for a in baselines},
                without_inter_arm_gaps_over_30s={a:compare(adjacent,a,candidate) for a in baselines})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory",type=Path)
    parser.add_argument("--output",type=Path)
    args = parser.parse_args()
    data = (json.dumps(summarize(args.directory),indent=2)+"\n").encode()
    if args.output:
        write_once(args.output,data)
    else:
        print(data.decode(),end="")
