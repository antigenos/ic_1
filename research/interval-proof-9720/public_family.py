"""Export per-function scientific measurements from an audited local research archive."""
import argparse
import csv
import json
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = list(measurements(args.archive))
    with args.output.open("x", encoding="utf8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(dict(rows=len(rows), verified_optima=sum(r["independently_proved_optimum"] for r in rows))))
