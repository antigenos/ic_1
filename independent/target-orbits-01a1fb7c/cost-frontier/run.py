"""Record a cold native process and its proof table without overwriting previous trials."""
import argparse
import ctypes
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import time


def peak_bytes(process):
    if platform.system() != 'Windows':
        return None
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (s, ctypes.c_size_t) for s in ('peak', 'working', 'peak_page', 'page',
                                           'peak_nonpage', 'nonpage', 'swap', 'peak_swap')]
    info = Counters()
    info.cb = ctypes.sizeof(info)
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(
        wintypes.HANDLE(int(process._handle)), ctypes.byref(info), info.cb)
    return info.peak if ok else None


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('exe', type=Path)
    p.add_argument('n', type=int)
    p.add_argument('cap', type=int)
    p.add_argument('mode', choices=['projected','uniform','direct'])
    p.add_argument('directory', type=Path)
    args = p.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    table = args.directory / 'table.tsv'
    switches = [str(args.n), str(args.cap)]
    if args.mode != 'direct':
        switches.append(args.mode)
    cmd = [str(args.exe.resolve()), *switches, str(table.resolve())]
    launch = dict(command=[args.exe.name, *switches, table.name], binary=digest(args.exe),
                  source=digest(Path(__file__).with_name('frontier.cpp')),
                  started=datetime.now(timezone.utc).isoformat(), host=platform.platform(),
                  processor=platform.processor())
    if args.mode=='direct':
        launch['direct_source']=digest(Path(__file__).with_name('direct.cpp'))
    start = time.perf_counter()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    (args.directory/'launch.json').write_text(json.dumps(dict(launch, pid=proc.pid), indent=2))
    out, err = proc.communicate()
    record = dict(launch, wall_s=time.perf_counter()-start, peak_working_bytes=peak_bytes(proc),
                  exit_code=proc.returncode, stdout=out.strip(), stderr=err.strip())
    if table.is_file():
        record['table_sha256'] = digest(table)
    (args.directory/'result.json').write_text(json.dumps(record, indent=2))
    print(json.dumps(record))
    raise SystemExit(proc.returncode)
