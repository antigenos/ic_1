"""Export per-function scientific measurements from an audited local research archive."""
import argparse
import csv
import json
import math
from pathlib import Path
from zipfile import ZipFile

from family import HERE, VERIFIED, summarize
from snapshot_family import verify

FIELDS = ("truth", "method", "outcome", "time_limit_s", "capped_elapsed_s", "activity",
          "gate_count", "independently_proved_optimum", "reused_trial")


def measurements(source):
    with ZipFile(source) as z:
        manifest = json.loads(z.read("manifest.json"))
        if "checkpoint.json" in z.namelist():
            verify(source)
            retained = json.loads(z.read("reused.json"))
            rows = list(retained.values())
            for truth, arm in json.loads(z.read("checkpoint.json"))["new_trials"]:
                rows.append(json.loads(z.read(f"records/{truth}/{arm}/result.json")))
        else:
            grouped = {arm: [json.loads(s) for s in z.read(arm+".jsonl").splitlines()] for arm in "AC"}
            assert summarize(grouped, manifest) == json.loads(z.read("summary.json"))
            rows = grouped["A"] + grouped["C"]
    reused_cases = {c["truth"] for c in manifest["cases"] if c["source"] != "new"}
    proofs = json.loads((HERE / "evidence/constructed-through-432.json").read_bytes())["circuits"]
    for row in sorted(rows, key=lambda r: (r["experiment"]["truth"], r["experiment"]["arm"])):
        truth = row["experiment"]["truth"]
        witness = row.get("witness", {})
        proved = int(bool(witness) and truth in proofs)
        if proved:
            assert witness["activity"] == proofs[truth]["witness"]["activity"]
        yield dict(truth=truth, method=row["experiment"]["arm"],
                   outcome="returned_verified_witness" if row["status"] == VERIFIED else "timeout",
                   time_limit_s=row["timeout_s"], capped_elapsed_s=row["capped_wall_s"],
                   activity=witness.get("activity", ""), gate_count=witness.get("gates", ""),
                   independently_proved_optimum=proved, reused_trial=int(truth in reused_cases))


def summarize_csv(source):
    plan = json.loads((HERE / "evidence/family-plan.json").read_bytes())
    expected = {c["truth"] for c in plan["cases"]}
    solved = "returned_verified_witness"
    arms = {"A": {}, "C": {}}
    with source.open(encoding="utf8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("Unexpected public measurement schema")
        for row in reader:
            truth, method, outcome = row["truth"], row["method"], row["outcome"]
            if truth not in expected or method not in arms or truth in arms[method]:
                raise ValueError(f"Unexpected or duplicate trial: {truth} {method}")
            cap, elapsed = float(row["time_limit_s"]), float(row["capped_elapsed_s"])
            if cap != plan["cap"] or not 0 < elapsed <= cap or outcome not in (solved, "timeout"):
                raise ValueError(f"Invalid timing or outcome for {truth} {method}")
            if row["independently_proved_optimum"] not in ("0","1") or row["reused_trial"] not in ("0","1"):
                raise ValueError(f"Invalid evidence flag for {truth} {method}")
            if outcome == solved:
                if not row["activity"].isdigit() or not row["gate_count"].isdigit() or int(row["gate_count"]) == 0:
                    raise ValueError(f"Missing circuit results for {truth} {method}")
            elif row["activity"] or row["gate_count"] or row["independently_proved_optimum"] != "0":
                raise ValueError(f"Unexpected circuit result for a timeout: {truth} {method}")
            arms[method][truth] = (outcome, elapsed, row["activity"])
    per_arm = {}
    for method, group in arms.items():
        per_arm[method] = dict(trials=len(group), completed=sum(r[0] == solved for r in group.values()),
                               capped_s=math.fsum(r[1] for r in group.values()))
    paired = sorted(arms["A"].keys() & arms["C"].keys())
    ratios, gained, lost = {}, [], []
    for truth in paired:
        a, c = arms["A"][truth], arms["C"][truth]
        if a[0] == c[0] == solved:
            if a[2] != c[2]:
                raise ValueError(f"Conflicting reported activities for {truth}")
            ratios[truth] = a[1] / c[1]
        elif a[0] != c[0]:
            (gained if c[0] == solved else lost).append(truth)
    return dict(expected_functions=len(expected), complete_family=len(paired) == len(expected),
                observed_trials=sum(len(g) for g in arms.values()), observed_pairs=len(paired), methods=per_arm,
                common=len(ratios), paired_gm=math.exp(math.fsum(map(math.log, ratios.values())) / len(ratios)) if ratios else None,
                gained=gained, lost=lost, slower={t:r for t,r in ratios.items() if r < 1})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--summary", action="store_true", help="Recompute the comparison directly from a public CSV")
    args = parser.parse_args()
    if args.summary:
        if args.output is not None:
            parser.error("--summary reads only the source CSV and prints JSON")
        print(json.dumps(summarize_csv(args.source), indent=2))
        raise SystemExit(0)
    if args.output is None:
        parser.error("Export requires an output CSV path")
    rows = list(measurements(args.source))
    with args.output.open("x", encoding="utf8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(dict(rows=len(rows), verified_optima=sum(r["independently_proved_optimum"] for r in rows))))
