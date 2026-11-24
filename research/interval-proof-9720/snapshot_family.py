"""Save verified trials from a running family experiment in a directly resumable archive."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from family import HERE, check_plan, reused, validate
from reserve_plan import BASE, known_manifest

FILES = ("request.json", "launch.json", "solver.log", "result.json", "verified.json")
FIELDS = {"request.json": {"start_utc", "binary_sha256", "command", "timeout_s", "experiment"},
          "launch.json": {"pid", "child_affinity"}, "verified.json": {"status", "wall_s"}}


def verify(archive):
    with ZipFile(archive) as z:
        manifest = json.loads(z.read("manifest.json"))
        check_plan(manifest)
        assert known_manifest(manifest)
        checkpoint = json.loads(z.read("checkpoint.json"))
        selected = {tuple(x) for x in checkpoint["new_trials"]}
        assert len(selected) == len(checkpoint["new_trials"])
        allowed = {"manifest.json", "checkpoint.json", "reused.json"}
        samples = []
        if checkpoint["host_samples"]:
            allowed.add("host-samples.jsonl")
            samples = [json.loads(s) for s in z.read("host-samples.jsonl").splitlines()]
            assert all(b["epoch"] > a["epoch"] for a, b in zip(samples, samples[1:]))
            assert all(set(s) == {"epoch", "occupied", "consecutive_free", "own_pids"} for s in samples)
            assert all(set(s["occupied"]) <= set(manifest["cpus"]) for s in samples)
        assert len(samples) == checkpoint["host_samples"]
        for truth, arm in selected:
            allowed.update(f"records/{truth}/{arm}/{name}" for name in FILES)
        assert len(z.namelist()) == len(allowed) and set(z.namelist()) == allowed
        retained = json.loads(z.read("reused.json"))
        assert retained == reused()
        seen = set()
        counts = Counter()
        certified = json.loads((HERE / "evidence/constructed-through-432.json").read_bytes())["circuits"]
        known_witnesses = 0
        for case in manifest["cases"]:
            truth = case["truth"]
            for arm in "AC":
                if case["source"] == "new":
                    if (truth, arm) not in selected:
                        continue
                    seen.add((truth, arm))
                    prefix = f"records/{truth}/{arm}/"
                    row = json.loads(z.read(prefix + "result.json"))
                    for name, keys in FIELDS.items():
                        receipt = json.loads(z.read(prefix + name))
                        assert set(receipt) == keys
                        assert all(row[k] == v for k, v in receipt.items())
                    log = z.read(prefix + "solver.log")
                    row.update(solver_output=log.decode(), solver_log_sha256=sha256(log).hexdigest())
                else:
                    row = retained[arm]
                validate(row, case, arm, manifest["binary_sha256"])
                counts[row["status"]] += 1
                if "witness" in row and truth in certified:
                    assert row["witness"]["activity"] == certified[truth]["witness"]["activity"]
                    known_witnesses += 1
        assert seen == selected
        return dict(verified=sum(counts.values()), retained=len(retained), status=dict(counts), host_samples=len(samples),
                    compared_with_independent_optimum=known_witnesses)


def save(archive, work, host_samples, source=BASE):
    if archive.exists():
        raise FileExistsError(archive)
    manifest = json.loads(source.read_bytes())
    assert known_manifest(manifest)
    check_plan(manifest)
    trials = [(case["truth"], arm) for case in manifest["cases"] if case["source"] == "new"
              for arm in case["order"] if (work / case["truth"] / arm / "verified.json").is_file()]
    tmp = archive.with_suffix(".partial")
    samples = []
    if host_samples is not None:
        samples = [s for s in host_samples.read_bytes().splitlines(keepends=True) if s.endswith(b"\n")]
    with ZipFile(tmp, "x", compression=ZIP_DEFLATED) as z:
        z.writestr("manifest.json", source.read_bytes())
        checkpoint = dict(captured_utc=datetime.now(timezone.utc).isoformat(), new_trials=trials, host_samples=len(samples))
        z.writestr("checkpoint.json", json.dumps(checkpoint))
        if samples:
            z.writestr("host-samples.jsonl", b"".join(samples))
        z.writestr("reused.json", json.dumps(reused()))
        for truth, arm in trials:
            for name in FILES:
                z.write(work / truth / arm / name, f"records/{truth}/{arm}/{name}")
    result = verify(tmp)
    tmp.rename(archive)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("save", "verify"))
    parser.add_argument("archive", type=Path)
    parser.add_argument("--work", type=Path, default=HERE / ".local/full-300")
    parser.add_argument("--manifest", type=Path, default=BASE)
    parser.add_argument("--samples", type=Path, help="Include complete host load samples up to the checkpoint")
    args = parser.parse_args()
    result = save(args.archive, args.work, args.samples, args.manifest) if args.action == "save" else verify(args.archive)
    print(json.dumps(result))
