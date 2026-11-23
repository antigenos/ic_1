"""Repair one terminal timing-overrun case without relaunching other running lanes."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

from family import PUBLIC,ROOT,WORK,run_lane,write_once
from summarize import replay


def main():
    p=argparse.ArgumentParser()
    p.add_argument("truth")
    p.add_argument("--resume-id",required=True)
    p.add_argument("--prepared",type=Path,default=ROOT)
    p.add_argument("--public",type=Path,default=PUBLIC)
    p.add_argument("--work",type=Path,default=WORK)
    args=p.parse_args()
    if not args.resume_id.isalnum(): p.error("Choose an alphanumeric recovery identifier")
    m=json.loads((args.public/"manifest.json").read_bytes())
    target=next(r for r in m["rows"] if r["truth"]==args.truth)
    lane=[r for r in m["rows"] if r["cpu"]==target["cpu"]]
    for r in lane[lane.index(target)+1:]:
        if (args.work/(r["truth"]+".jsonl")).exists():
            raise ValueError("Lane already continued after the specified case")
    path=args.work/(args.truth+".jsonl")
    lines=path.read_bytes().splitlines(keepends=True)
    bad=json.loads(lines[-1])
    assert b"Invalid timing or witness" in (args.work/(args.truth+".launcher.log")).read_bytes()
    assert bad["status"]=="timeout" and bad["wall_s"]>bad["timeout_s"]+3
    assert bad["experiment"]==dict(truth=args.truth,cpu=target["cpu"],arm=target["order"][len(lines)-1],order=len(lines))
    raw=args.work/"raw"/args.truth
    matches=[json.loads(q.read_bytes()) for q in raw.rglob("result.json")]
    assert any(r["pid"]==bad["pid"] and r["start_utc"]==bad["start_utc"] and r["returncode"]==bad["returncode"]
               and r["status"]=="timeout" for r in matches)
    if os.name=="nt":
        cmd=f"Get-Process -Id {int(bad['pid'])} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty StartTime | ForEach-Object {{ $_.ToUniversalTime().ToString('o') }}"
        info=subprocess.run(["powershell","-NoProfile","-Command",cmd],capture_output=True,text=True).stdout.strip()
        if info and datetime.fromisoformat(info)<=datetime.fromisoformat(bad["start_utc"]):
            raise RuntimeError("Original PID is still active")
    elif Path("/proc",str(bad["pid"])).exists():
        raise RuntimeError("Inspect active or reused process ID before recovery")
    backup=args.work/"recovery"/args.resume_id/path.name
    write_once(backup,path.read_bytes())
    write_once(args.public/"recovery"/(args.truth+"-"+args.resume_id+".json"),
               (json.dumps(dict(reason="timeout wall exceeded the preregistered cap plus three seconds",
                                retained_prefix=len(lines)-1,discarded=bad),indent=2)+"\n").encode())
    tmp=path.with_suffix("."+args.resume_id+".tmp")
    write_once(tmp,b"".join(lines[:-1]))
    replay(tmp,args.truth,target["order"][:len(lines)-1],target["cpu"],target["seconds"])
    os.replace(tmp,path)
    run_lane(lane[lane.index(target):],args,m["binary_sha256"])


if __name__=="__main__":
    main()
