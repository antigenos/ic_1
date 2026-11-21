"""Time one author CLI call, preserve its output and validate its witness."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone

from witness import simulate


def child_cpus(process):
    if os.name != "nt":
        return sorted(os.sched_getaffinity(process.pid))
    current, system = ctypes.c_size_t(), ctypes.c_size_t()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = ctypes.c_void_p(int(process._handle))
    if not kernel.GetProcessAffinityMask(handle, ctypes.byref(current), ctypes.byref(system)):
        raise ctypes.WinError(ctypes.get_last_error())
    return [cpu for cpu in range(ctypes.sizeof(current)*8) if current.value & (1 << cpu)]


def run(binary, truth, n, mode, timeout, dest, *, env=None, metadata=None):
    target = int(truth, 16)
    if not 0 <= target < (1 << (1 << n)):
        raise ValueError("Truth table outside the requested input width")
    truth = f"{target:0{(1 << n)//4}x}"
    binary = Path(binary).resolve(strict=True)
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    dest.mkdir(parents=True, exist_ok=False)
    command = [str(binary), "-c", f"pexact -I {n} -M {mode} {truth}"]
    result = {"start_utc": datetime.now(timezone.utc).isoformat(), "binary_sha256": digest,
              "command": [binary.name, *command[1:]], "timeout_s": timeout}
    if metadata is not None:
        result["experiment"] = metadata
    (dest / "request.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    start = time.perf_counter()
    with (dest / "solver.log").open("wb") as log, subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT, cwd=dest, env=env) as p:
        try:
            launch = {"pid": p.pid}
            if metadata is not None and "cpu" in metadata:
                launch["child_affinity"] = child_cpus(p)
                if launch["child_affinity"] != [metadata["cpu"]]:
                    raise RuntimeError(f"Unexpected child CPU allocation: {launch}")
            result.update(launch)
            (dest / "launch.json").write_text(json.dumps(launch), encoding="utf-8")
            p.wait(timeout=max(0, timeout - (time.perf_counter() - start)))
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
            result["status"] = "timeout"
        except BaseException:
            p.kill()
            p.wait()
            raise
        result["returncode"] = p.returncode
    elapsed = time.perf_counter() - start
    result.update(wall_s=elapsed, capped_wall_s=min(elapsed, timeout))
    if "status" not in result:
        output = (dest / "solver.log").read_text(encoding="utf-8", errors="replace")
        try:
            if p.returncode or "Total runtime" not in output:
                raise ValueError("Author search did not report a completed run")
            result["witness"] = simulate(output, n, target)
            result["status"] = "solver_completed_verified_witness"
        except ValueError as exc:
            result.update(status="unverified", reason=str(exc))
    (dest / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("binary")
    parser.add_argument("truth")
    parser.add_argument("dest", type=Path)
    parser.add_argument("--inputs", type=int, choices=[2, 3, 4], default=4)
    parser.add_argument("--mode", type=int, choices=[0, 1, 2], default=2)
    parser.add_argument("--seconds", type=float, default=30)
    args = parser.parse_args()
    result = run(args.binary, args.truth, args.inputs, args.mode, args.seconds, args.dest)
    print(json.dumps(result))
    raise SystemExit(0 if result["status"] == "solver_completed_verified_witness" else 1)
