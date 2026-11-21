"""Run the 208-function confirmation with per-case raw logs and safe resumption."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from compare_orbits import HERE, ROOT
from repeat_0189 import pin
from run_case import run
from compare import dump

CPUS=tuple(range(16,32,2))
DEST=ROOT/".local/orbit-confirmation-300"
SUFFIX=".exe" if os.name=="nt" else ""
BINS={a:ROOT/".local/variants"/d/("abc"+SUFFIX) for a,d in (("A","orbit-control"),("B","orbit-signed"))}


@contextmanager
def lock(path):
    with path.open("a+b") as f:
        f.seek(0)
        if os.name=="nt":
            import msvcrt
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def awake():
    if os.name!="nt":
        return time.monotonic()
    value=ctypes.c_uint64()
    if not ctypes.windll.kernel32.QueryUnbiasedInterruptTime(ctypes.byref(value)):
        raise ctypes.WinError()
    return value.value*1e-7


def digests():
    return {a:hashlib.sha256(p.read_bytes()).hexdigest() for a,p in BINS.items()}


def work(cpu,cases,hashes):
    pin(cpu)
    for case in cases:
        if case["cpu"]!=cpu:
            continue
        t=case["truth"]
        for pos,arm in enumerate(case["order"],1):
            folder=DEST/t/f"{pos}-{arm}"
            meta=dict(cpu=cpu,truth=t,arm=arm,order=pos)
            if folder.exists():
                if not (folder/"accepted.json").exists():
                    raise RuntimeError(f"Unfinished attempt requires inspection: {folder}")
                r=json.loads((folder/"result.json").read_text())
                if (r["experiment"]!=meta or r["binary_sha256"]!=hashes[arm] or r["timeout_s"]!=300
                        or not json.loads((folder/"accepted.json").read_text())["valid"]):
                    raise ValueError(folder)
                continue
            env={k:v for k,v in os.environ.items() if not k.startswith(("REPLAY_","PEXACT_ORBIT","PEXACT_PREFIX"))}
            env["PEXACT_ORBIT"]="signed" if arm=="B" else "off"
            utc0,up0=time.time(),awake()
            r=run(BINS[arm],t,4,2,300,folder,env=env,metadata=meta)
            dt,du=time.time()-utc0,awake()-up0
            valid=(abs(dt-du)<5 and r["wall_s"]<=303 and r["binary_sha256"]==hashes[arm]
                   and r["status"] in ("timeout","solver_completed_verified_witness"))
            dump(folder/"accepted.json",dict(valid=valid,utc_elapsed=dt,awake_elapsed=du))
            if not valid:
                raise ValueError(f"Retain and inspect invalid attempt: {folder}")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--lane",type=int)
    a=p.parse_args()
    ts=json.loads((HERE/"reproduction/evidence/npn-family.json").read_text())["essential"]
    assert len(ts)==len(set(ts))==208
    cases=[dict(truth=t,cpu=CPUS[i%8],order="AB" if (i//8+i%8)%2==0 else "BA") for i,t in enumerate(ts)]
    conf=dict(cpus=CPUS,cap=300,binaries=digests(),platform=platform.platform())
    DEST.mkdir(parents=True,exist_ok=True)
    if a.lane is not None:
        if a.lane not in CPUS:
            raise ValueError(a.lane)
        with lock(DEST/f"lane-{a.lane}.lock"):
            work(a.lane,cases,conf["binaries"])
        return
    with lock(DEST/"batch.lock"):
        for name,data in (("manifest.json",cases),("configuration.json",conf)):
            path=DEST/name
            if path.exists():
                assert json.loads(path.read_text())==json.loads(json.dumps(data))
            else:
                dump(path,data)
        with ThreadPoolExecutor(max_workers=len(CPUS)) as pool:
            def launch(cpu):
                subprocess.run([sys.executable,__file__,"--lane",str(cpu)],check=True)
            list(pool.map(launch,CPUS))
        assert len(list(DEST.glob("*/*/accepted.json")))==416
        print("All 416 paired observations have terminal records.")


if __name__=="__main__":
    main()
