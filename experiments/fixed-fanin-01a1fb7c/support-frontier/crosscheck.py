"""Compare live-postfix optima with every class in a bounded forward search."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from audit import literals_cached, maps
from run import digest, pin


def signed_images(n, t):
    rows = 1 << n
    mask = (1 << rows) - 1
    for order in maps(n):
        images = [sum(((t >> src) & 1) << i for i, src in enumerate(order))]
        for i, high in enumerate(literals_cached(n)):
            images += [((x & high) >> (1 << i)) | ((x & (mask ^ high)) << (1 << i))
                       for x in images]
        for x in images:
            yield mask ^ x if x & 1 else x


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    ref = json.loads(args.reference.read_text())
    assert ref["witness_audit"] and ref["terminal"]=="complete"
    n, cap = ref["n"], ref["cap"]
    pin(ref["cpu"])
    record = dict(n=n, cap=cap, cpu=ref["cpu"], binary_sha256=digest(args.binary),
                  reference_sha256=digest(args.reference), timeout_s=args.timeout)
    start = time.perf_counter()
    try:
        run = subprocess.run([str(args.binary.resolve()), str(n),str(cap)],
                             capture_output=True, timeout=args.timeout,check=True)
    except subprocess.TimeoutExpired:
        record.update(status="timeout", wall_s=time.perf_counter()-start)
        args.output.write_text(json.dumps(record,indent=2)+"\n")
        print(n,cap,record)
        return
    record["solver_wall_s"] = time.perf_counter()-start
    lookup = {}
    expected = {}
    for w in ref["witnesses"]:
        rep = int(w["rep"],16)
        expected[rep] = w["cost"]
        for image in set(signed_images(n,rep)):
            assert lookup.setdefault(image,rep)==rep
    observed = {}
    raw_count = 0
    for line in run.stdout.decode().splitlines():
        if line.startswith("stats "):
            _, visits, completed = line.split()
            record.update(visits=int(visits),live_expressions=int(completed))
        else:
            truth, cost = line.split()
            rep = lookup[int(truth,16)]
            cost = int(cost)
            observed[rep] = min(observed.get(rep, cost), cost)
            raw_count += 1
    assert observed==expected and "visits" in record
    record.update(total_wall_s=time.perf_counter()-start, status="all_optima_identical",
                  represented_labeled_outputs=raw_count, classes=len(observed),
                  stdout_sha256=hashlib.sha256(run.stdout).hexdigest())
    args.output.write_text(json.dumps(record,indent=2)+"\n")
    print(n,cap,record)


if __name__ == "__main__":
    main()
