"""Run cold processes on one pinned core and store results before auditing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from audit import check_witness, compare_reference

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from repeat_0189 import pin


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("n", type=int)
    parser.add_argument("cap", type=int)
    parser.add_argument("mode", type=int)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cpu", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    outfile = args.output
    outfile.parent.mkdir(parents=True, exist_ok=True)
    if outfile.exists():
        raise FileExistsError(outfile)
    pin(args.cpu)
    binary = args.binary.resolve()
    record = dict(n=args.n, cap=args.cap, mode=args.mode, cpu=args.cpu,
                  binary_sha256=digest(binary), platform=platform.platform(),
                  source_sha256=digest(HERE / "frontier.cpp"), timeout_s=args.timeout,
                  start_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()))
    start = time.perf_counter()
    try:
        run = subprocess.run([str(binary), str(args.n), str(args.cap), str(args.mode)],
                             capture_output=True, text=True, timeout=args.timeout, check=True)
    except subprocess.TimeoutExpired:
        record.update(wall_s=time.perf_counter()-start, terminal="timeout")
        outfile.write_text(json.dumps(record, indent=2)+"\n")
        print(record)
        return
    record["wall_s"] = time.perf_counter()-start
    witnesses = []
    stats = None
    for line in run.stdout.splitlines():
        kind, *values = line.split()
        if kind == "opt":
            rep, truth, cost, *gates = values
            witnesses.append(dict(rep=rep, truth=truth, cost=int(cost),
                                  gates=[list(map(int, g.split(","))) for g in gates]))
        elif kind == "stats":
            stats = dict(zip(("states","cut","forced","pair_rejections"),map(int,values),strict=True))
        else:
            raise ValueError(line)
    assert stats is not None
    record.update(terminal="complete", stats=stats, witnesses=witnesses)
    outfile.write_text(json.dumps(record,separators=(",",":"))+"\n")
    started_audit = time.perf_counter()
    for item in witnesses:
        check_witness(args.n, item)
    observed = {int(w["rep"],16):w["cost"] for w in witnesses}
    assert len(observed)==len(witnesses)
    compare_reference(args.n,args.cap,observed)
    record.update(witness_audit=True, small_reference_audit=args.n in {3,4},
                  audit_s=time.perf_counter()-started_audit)
    outfile.write_text(json.dumps(record,separators=(",",":"))+"\n")
    print(args.n,args.cap,args.mode,stats,len(witnesses),record["wall_s"],record["audit_s"])


if __name__ == "__main__":
    main()
