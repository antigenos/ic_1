"""Run the registered cold comparisons for direct terminal output matching."""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from family import HERE, pin, simulate, wait_for_quiet_cpu
from run_case import child_cpus
from terminal_checks import check

CONTROL = "f8c6a8601ad8e07e31c438256f954dcc73cbd474"
MODULES = ("cold_bounds.py", "construct_bounds.py", "family_bounds.py")
PLAN = [("0189", 305, arm) for arm in "ATTA"] + [("0016", 433, arm) for arm in "TA"]
BOOT = """
import os, runpy, sys
from pathlib import Path
source, lab = sys.argv[1:3]
def guard(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        if Path(os.fsdecode(args[0])).suffix.lower() in {'.json','.jsonl','.zip','.log','.csv','.bin','.npy','.npz','.pkl'}:
            raise RuntimeError('Cold process attempted to open benchmark data')
sys.addaudithook(guard)
sys.path[:0] = [source, lab]
script = str(Path(source) / 'cold_bounds.py')
sys.argv = [script, *sys.argv[3:]]
runpy.run_path(script, run_name='__main__')
"""


def sources(work, arm):
    dest = work / "source" / arm
    dest.mkdir(parents=True)
    digests = {}
    for name in MODULES:
        if arm == "A":
            path = (HERE / name).relative_to(HERE.parents[1]).as_posix()
            data = subprocess.check_output(["git", "cat-file", "blob", f"{CONTROL}:{path}"], cwd=HERE)
        else:
            data = (HERE / name).read_bytes().replace(b"\r\n", b"\n")
        (dest / name).write_bytes(data)
        digests[name] = sha256(data).hexdigest()
    return dest, digests


def holdout_plan(bounds):
    old = json.loads((HERE / "evidence/confirmation-plan.json").read_bytes())
    excluded = {c["truth"] for c in old["cases"]} | {"0001", "0006", "0016", "001e", "0189", "018b"}
    strata = [[] for _ in range(4)]
    for truth, value in bounds["lower_bounds"].items():
        if truth not in excluded:
            group = 0 if value <= 305 else 1 if value < 432 else 2 if value == 432 else 3
            strata[group].append(truth)
    cases = []
    for group, truths in enumerate(strata):
        order = sorted(truths, key=lambda t: sha256(("9720-terminal-holdout/"+t).encode()).digest())
        for truth, arms in zip(order[:2], ("AT", "TA")):
            cases.append(dict(truth=truth, stratum=group, order=arms))
    assert len(cases) == 8 and bounds["strict_cap"] == 433
    return dict(strict_cap=433, wall_cap_s=300, cases=cases)


def checked_answer(row, bounds):
    assert row["exitcode"] == 0 and not row["stderr"] and 0 < row["wall_s"] <= 300
    truth, cap, arm = row["truth"], row["strict_cap"], row["arm"]
    answer = json.loads(row["stdout"])
    assert answer["truth"] == truth and answer["strict_cap"] == cap
    expected = min(bounds["lower_bounds"][truth], cap)
    assert answer["lower_bound"] == expected
    if expected < cap:
        witness = simulate(answer["circuit"], 4, int(truth, 16))
        assert answer["status"] == "independently_optimal" and witness == answer["witness"]
        assert witness["activity"] == expected
    else:
        assert answer["status"] == "no_solution_below_cap" and "witness" not in answer and "circuit" not in answer
    limit = cap - 30 if arm == "T" else cap
    assert answer["states"] == sum(n for cost, n in bounds["states_by_cost"].items() if int(cost) < limit)
    return answer


def export(source, destination, plan, bounds):
    rows = [json.loads(s) for s in source.read_bytes().splitlines()]
    assert [(r["truth"], r["strict_cap"], r["arm"]) for r in rows] == plan
    public = []
    for i, r in enumerate(rows, 1):
        truth, cap, arm = plan[i-1]
        assert r["order"] == i and r["timeout_s"] == 300
        item = dict(order=i, truth=truth, method="terminal_output_matching" if arm == "T" else "full_enumeration",
                    strict_activity_cap=cap, timeout_s=300, outcome=r["status"],
                    capped_elapsed_s=min(300., r["wall_s"]), optimum="", gates="", expanded_states="", terminal_edges="")
        if r["status"] == "completed":
            answer = checked_answer(r, bounds)
            witness = answer.get("witness", {})
            if not witness:
                item["outcome"] = "proved_no_solution_below_cap"
            item.update(optimum=witness.get("activity", ""), gates=witness.get("gates", ""), expanded_states=answer["states"],
                        terminal_edges=answer.get("terminal_edges", ""))
        else:
            assert r["status"] == "timeout" and r["wall_s"] >= 299.95
        public.append(item)
    with destination.open("x", encoding="utf8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(public[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(public)
    return public


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--cpu", type=int)
    ap.add_argument("--host-samples", type=Path)
    ap.add_argument("--holdout", action="store_true", help="Use the fixed eight-function confirmation panel")
    ap.add_argument("--register-holdout", action="store_true", help="Write the deterministic confirmation manifest")
    ap.add_argument("--public-csv", type=Path, help="Verify a finished local run and export its scientific measurements")
    args = ap.parse_args()
    bounds = json.loads((HERE / "evidence/constructed-through-432.json").read_bytes())["bounds"]
    if args.register_holdout:
        with args.output.open("x", encoding="utf8", newline="\n") as f:
            json.dump(holdout_plan(bounds), f, indent=2)
            f.write("\n")
        return
    plan = PLAN
    if args.holdout:
        registered = json.loads((HERE / "evidence/terminal-holdout-plan.json").read_bytes())
        assert registered == holdout_plan(bounds)
        plan = [(c["truth"], registered["strict_cap"], arm) for c in registered["cases"] for arm in c["order"]]
    if args.public_csv:
        rows = export(args.output, args.public_csv, plan, bounds)
        print(json.dumps(dict(verified_trials=len(rows))))
        return
    if args.cpu is None:
        ap.error("Running the trials requires --cpu")
    pin(args.cpu)
    work = HERE / ".local/terminal-comparisons" / args.output.stem
    if args.output.exists():
        raise FileExistsError(args.output)
    work.mkdir(parents=True, exist_ok=False)
    source = {arm: sources(work, arm) for arm in "AT"}
    samples = args.host_samples.resolve() if args.host_samples else None
    if samples is not None:
        samples.mkdir(parents=True, exist_ok=True)
        with (samples / "controller.json").open("x") as f:
            json.dump(dict(pid=os.getpid(), started=time.time(), cpus=[args.cpu]), f)
    wait_for_quiet_cpu(args.cpu, samples)
    (work / "correctness.json").write_text(json.dumps(check(), indent=2) + "\n", encoding="utf8")
    with args.output.open("x", encoding="utf8", newline="\n") as evidence:
        for i, (truth, cap, arm) in enumerate(plan, 1):
            wait_for_quiet_cpu(args.cpu, samples)
            empty = work / f"empty-{i}"
            empty.mkdir()
            directory, hashes = source[arm]
            cmd = [sys.executable, "-I", "-B", "-c", BOOT, str(directory), str(HERE), truth,
                   "--cap", str(cap), "--cpu", str(args.cpu)]
            if arm == "T":
                cmd.append("--terminal")
            row = dict(order=i, truth=truth, arm=arm, strict_cap=cap, timeout_s=300,
                       source_sha256=hashes, start_utc=datetime.now(timezone.utc).isoformat())
            start = time.perf_counter()
            with subprocess.Popen(cmd, cwd=empty, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as p:
                try:
                    row.update(pid=p.pid, child_affinity=child_cpus(p))
                    assert row["child_affinity"] == [args.cpu]
                    (work / f"launch-{i}.json").write_text(json.dumps(row))
                    stdout, stderr = p.communicate(timeout=max(0, 300-(time.perf_counter()-start)))
                    row["status"] = "completed"
                except subprocess.TimeoutExpired:
                    p.kill()
                    stdout, stderr = p.communicate()
                    row["status"] = "timeout"
                except BaseException:
                    p.kill()
                    p.wait()
                    raise
                row.update(wall_s=time.perf_counter()-start, exitcode=p.returncode, stdout=stdout, stderr=stderr)
            evidence.write(json.dumps(row) + "\n")
            evidence.flush()
            if row["status"] == "completed":
                checked_answer(row, bounds)
            print(truth, arm, row["status"], round(row["wall_s"], 3), flush=True)
    if samples is not None:
        finished = time.time()
        deadline = time.monotonic() + 55
        while time.monotonic() < deadline:
            try:
                if json.loads((samples / "latest.json").read_bytes())["epoch"] >= finished:
                    break
            except (FileNotFoundError, PermissionError):
                pass
            time.sleep(2)


if __name__ == "__main__":
    main()
