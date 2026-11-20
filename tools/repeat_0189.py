"""Execute the registered E08-R two-order comparison on one logical CPU."""
import argparse
import ctypes
import json
import os
from pathlib import Path

from run_case import run


def pin(cpu):
    if os.name != "nt":
        os.sched_setaffinity(0, {cpu})
        assert os.sched_getaffinity(0) == {cpu}
        return
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    process = ctypes.c_void_p(-1)
    mask = ctypes.c_size_t(1 << cpu)
    if not k.SetProcessAffinityMask(process, mask):
        raise ctypes.WinError(ctypes.get_last_error())
    current, system = ctypes.c_size_t(), ctypes.c_size_t()
    if not k.GetProcessAffinityMask(process, ctypes.byref(current), ctypes.byref(system)):
        raise ctypes.WinError(ctypes.get_last_error())
    if current.value != mask.value:
        raise RuntimeError("Affinity readback differs")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("author", type=Path)
    p.add_argument("candidate", type=Path)
    p.add_argument("dest", type=Path)
    p.add_argument("--cpu", type=int, default=2)
    args = p.parse_args()
    pin(args.cpu)
    args.dest.mkdir(parents=True, exist_ok=False)
    records = []
    for idx, label in enumerate("ABBA", 1):
        binary = args.author if label == "A" else args.candidate
        record = run(binary, "0189", 4, 2, 60, args.dest / f"{idx}-{label}")
        records.append(dict(order=idx, label=label, logical_cpu=args.cpu, **record))
        (args.dest / "summary.json").write_text(json.dumps(records, indent=2) + "\n",
                                                encoding="utf-8")
        if record.get("witness", {}).get("activity") != 304:
            raise RuntimeError("E08-R requires review: " + record["status"])
