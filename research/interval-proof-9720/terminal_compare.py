"""Run the registered cold comparisons for direct terminal output matching."""
import argparse
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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--cpu", type=int, required=True)
    ap.add_argument("--host-samples", type=Path)
    args = ap.parse_args()
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
        for i, (truth, cap, arm) in enumerate(PLAN, 1):
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
                assert row["exitcode"] == 0 and not stderr and row["wall_s"] <= 300
                answer = json.loads(stdout)
                expected = 304 if truth == "0189" else 406
                witness = simulate(answer["circuit"], 4, int(truth, 16))
                assert answer["status"] == "independently_optimal" and witness == answer["witness"]
                assert witness["activity"] == answer["lower_bound"] == expected
            print(truth, arm, row["status"], round(row["wall_s"], 3), flush=True)


if __name__ == "__main__":
    main()
