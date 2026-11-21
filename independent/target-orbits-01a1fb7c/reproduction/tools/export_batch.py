"""Export complete case records and original solver text without machine-local paths."""
import argparse
import hashlib
import json
from pathlib import Path

from compare import load, dump, summary


def export(src, dest):
    plan = load(src / "manifest.json")
    result = summary(src, plan)
    if result != load(src / "summary.json"):
        raise ValueError("Batch summary does not match the original records")
    dest.mkdir(parents=True, exist_ok=True)
    dump(dest / "manifest.json", plan)
    dump(dest / "summary.json", result)
    for method in plan["methods"]:
        output = []
        for truth in plan["cases"]:
            case = src / truth / method
            row = load(case / "result.json")
            raw = (case / "solver.log").read_bytes()
            row["solver_output"] = raw.decode("utf-8")
            row["solver_log_sha256"] = hashlib.sha256(raw).hexdigest()
            output.append(json.dumps(row, ensure_ascii=True, separators=(",", ":")))
        (dest / (method + ".jsonl")).write_bytes(("\n".join(output) + "\n").encode("utf-8"))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("batch", type=Path)
    p.add_argument("dest", type=Path)
    args = p.parse_args()
    export(args.batch, args.dest)
