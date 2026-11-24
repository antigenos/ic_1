"""Record a prospective CPU reassignment for completely untouched pairs."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from family import HERE

BASE = HERE / "evidence/family-plan.json"
REGISTER = HERE / "evidence/family-spare-core.json"
SEED = "9720-spare-core/"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def register(base, started, cpu):
    candidates = {c["truth"] for c in base["cases"] if c["source"] == "new"}
    assert cpu >= 0 and cpu not in base["cpus"] and started <= candidates
    eligible = sorted(candidates - started, key=lambda t: hashlib.sha256((SEED+t).encode()).digest())
    selected = eligible[:len(eligible)//(len(base["cpus"])+1)]
    return dict(base_digest=digest(base), spare_cpu=cpu, seed=SEED,
                previously_started=sorted(started), selected=selected)


def amended(base, record):
    assert record == register(base, set(record["previously_started"]), record["spare_cpu"])
    result = deepcopy(base)
    result["cpus"].append(record["spare_cpu"])
    selected = set(record["selected"])
    for case in result["cases"]:
        if case["truth"] in selected:
            case["cpu"] = record["spare_cpu"]
    return result


def known_manifest(manifest):
    base = json.loads(BASE.read_bytes())
    return manifest == base or (REGISTER.is_file() and manifest == amended(base, json.loads(REGISTER.read_bytes())))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("register","apply"))
    cli.add_argument("output", type=Path)
    cli.add_argument("--record", type=Path, default=REGISTER)
    cli.add_argument("--work", type=Path, default=HERE/".local/full-300")
    args = cli.parse_args()
    base = json.loads(BASE.read_bytes())
    if args.action == "register":
        interrupted = HERE/"evidence/family-interruptions.jsonl"
        started = {json.loads(line)["request"]["experiment"]["truth"] for line in interrupted.read_bytes().splitlines()}
        started.update(c["truth"] for c in base["cases"] if c["source"] == "new" and (args.work/c["truth"]).exists())
        result = register(base, started, 2)
    else:
        result = amended(base, json.loads(args.record.read_bytes()))
    with args.output.open("x", encoding="utf8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
