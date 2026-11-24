"""Recompute the all-family comparison after excluding pairs with uncertain host load."""
from argparse import ArgumentParser
from bisect import bisect_left, bisect_right
from collections import Counter
from datetime import datetime
import json
from math import exp, fsum, log
from pathlib import Path
from zipfile import ZipFile

from family import HERE, VERIFIED, summarize


def timestamp(row):
    return datetime.fromisoformat(row["start_utc"]).timestamp()


def exposure(row, samples, epochs):
    start = timestamp(row)
    end = start + row["wall_s"]
    left = bisect_right(epochs, start) - 1
    right = bisect_left(epochs, end)
    cpu = row["experiment"]["cpu"]
    flags = set()
    if left < 0 or right == len(samples):
        flags.add("missing_boundary")
    window = samples[max(0, left):right + 1]
    if any(str(cpu) not in sample["consecutive_free"] for sample in window):
        flags.add("unmonitored_cpu")
    if any(b["epoch"] - a["epoch"] > 45 for a, b in zip(window, window[1:])):
        flags.add("sampling_gap")
    for sample in window:
        if not start - 45 <= sample["epoch"] <= end + 45 or cpu not in sample["occupied"]:
            continue
        if start <= sample["epoch"] <= end and row["pid"] in sample["own_pids"]:
            flags.add("observed_overlap")
        else:
            flags.add("busy_near_measurement")
    return flags


def metrics(pairs):
    methods = {}
    for arm in "AC":
        methods[arm] = {
            "completed": sum(pair[arm]["status"] == VERIFIED for pair in pairs),
            "capped_s": fsum(pair[arm]["capped_wall_s"] for pair in pairs),
        }
    common = [p for p in pairs if all(p[k]["status"] == VERIFIED for k in "AC")]
    logs = [log(p["A"]["wall_s"] / p["C"]["wall_s"]) for p in common]
    return dict(pairs=len(pairs), methods=methods, common=len(common),
                paired_gm=exp(fsum(logs) / len(logs)) if logs else None)


def main():
    cli = ArgumentParser(description=__doc__)
    cli.add_argument("archive", type=Path)
    cli.add_argument("samples", type=Path, nargs="+", help="Chronological sample files, one per continuous controller session")
    cli.add_argument("--interruptions", type=Path, default=HERE / "evidence/family-interruptions.jsonl")
    args = cli.parse_args()
    sessions = [[json.loads(line) for line in path.read_bytes().splitlines()] for path in args.samples]
    if not all(sessions):
        cli.error("Every host sampling session must contain observations")
    samples = [sample for session in sessions for sample in session]
    epochs = [s["epoch"] for s in samples]
    assert epochs and all(b > a for a, b in zip(epochs, epochs[1:]))
    events = [json.loads(line) for line in args.interruptions.read_bytes().splitlines()]
    resumes = [min(timestamp(e["request"]) for e in events if e["reason"] == "shared-cpu-01")]
    resumes.extend(session[0]["epoch"] for session in sessions[1:])
    with ZipFile(args.archive) as z:
        manifest = json.loads(z.read("manifest.json"))
        rows = {k: [json.loads(line) for line in z.read(k + ".jsonl").splitlines()] for k in "AC"}
        primary = summarize(rows, manifest)
        assert primary == json.loads(z.read("summary.json"))
    indexed = {k: {r["experiment"]["truth"]: r for r in group} for k, group in rows.items()}
    all_pairs, clear, exclusions = [], [], {}
    base = json.loads((HERE/"evidence/family-plan.json").read_bytes())
    original_cpu = {c["truth"]: c["cpu"] for c in base["cases"]}
    groups = {"original_assignment": [], "spare_core": []}
    for case in manifest["cases"]:
        truth = case["truth"]
        pair = {k: indexed[k][truth] for k in "AC"}
        all_pairs.append(pair)
        groups["original_assignment" if case["cpu"] == original_cpu[truth] else "spare_core"].append(pair)
        flags = set().union(*(exposure(row, samples, epochs) for row in pair.values()))
        starts = [timestamp(row) for row in pair.values()]
        if any(min(starts) < resumed <= max(starts) for resumed in resumes):
            flags.add("across_pause")
        if flags:
            exclusions[truth] = sorted(flags)
        else:
            clear.append(pair)
    counts = Counter(flag for flags in exclusions.values() for flag in flags)
    result = dict(all_pairs=metrics(all_pairs), clear_pairs=metrics(clear),
                  by_assignment={label: metrics(group) for label, group in groups.items()},
                  excluded_counts=counts, excluded_pairs=exclusions)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
