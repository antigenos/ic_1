"""Match optional Windows working-set observations to individual accepted cold runs."""
import argparse
from collections import defaultdict
from datetime import datetime
import gzip
from hashlib import sha256
import json
from pathlib import Path

from family import HERE, write_once


def summarize(public, sample_bytes):
    rows = (public/"runs.jsonl").read_bytes().replace(b"\r\n", b"\n")
    summary = json.loads((public/"summary.json").read_bytes())
    assert sha256(rows).hexdigest() == summary["raw_sha256"]
    by_pid = defaultdict(list)
    counts = defaultdict(int)
    for line in rows.splitlines():
        run = json.loads(line)
        by_pid[run["pid"]].append(run)
        counts[run["experiment"]["arm"]] += 1
    captured = {}
    unmatched = 0
    for line in sample_bytes.splitlines():
        sample = json.loads(line)
        made = datetime.fromisoformat(sample["created_utc"])
        observed = datetime.fromisoformat(sample["sample_utc"])
        assert observed >= made and sample["peak_working_set_bytes"] > 0
        matches = []
        for run in by_pid[sample["pid"]]:
            start = datetime.fromisoformat(run["start_utc"])
            if -0.05 <= (made-start).total_seconds() <= min(5.0,run["wall_s"]+0.05):
                matches.append(run)
        if not matches:
            unmatched += 1
            continue
        assert len(matches) == 1
        exp = matches[0]["experiment"]
        key = (exp["truth"],exp["arm"])
        entry = captured.setdefault(key,dict(truth=key[0],arm=key[1],observations=0,peak_at_sample_bytes=0))
        entry["observations"] += 1
        entry["peak_at_sample_bytes"] = max(entry["peak_at_sample_bytes"],sample["peak_working_set_bytes"])
    by_arm = {}
    for arm,total in sorted(counts.items()):
        known = [r for r in captured.values() if r["arm"] == arm]
        by_arm[arm] = dict(total=total,observed=len(known),highest_observed_bytes=max(
            (r["peak_at_sample_bytes"] for r in known),default=None))
    return dict(run_sha256=summary["raw_sha256"],sample_sha256=sha256(sample_bytes).hexdigest(),
                unmatched_observations=unmatched,by_arm=by_arm,
                paired_observed=sum((t,"5") in captured for t,a in captured if a=="3"),
                runs=[captured[k] for k in sorted(captured)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--public",type=Path,default=HERE/"proof-full")
    parser.add_argument("--capture",type=Path,help="Export one finished sampler log; otherwise verify the published data")
    args = parser.parse_args()
    archive = args.public/"working-set.jsonl.gz"
    report = args.public/"working-set.json"
    if args.capture:
        raw = args.capture.read_bytes().replace(b"\r\n",b"\n")
        data = summarize(args.public,raw)
        write_once(archive,gzip.compress(raw,mtime=0))
        write_once(report,(json.dumps(data,indent=2)+"\n").encode())
    else:
        data = summarize(args.public,gzip.decompress(archive.read_bytes()))
        assert data == json.loads(report.read_bytes())
    print(json.dumps(data["by_arm"]))
