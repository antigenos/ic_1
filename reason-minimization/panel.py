"""Time complete invocations only on a vacant physical core; keep diagnostics separate."""
import argparse, ctypes, gzip, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
from build import D, ROOT, REF, CACHE, sha
from guard import cores,competitors
from audit import check
from repeat_0189 import pin
from run_case import run

cases=("0189","0019","001e","006b")
roles=("joint","short","online")
truth_bounds={"0189":304,"0019":310,"001e":224,"006b":432}
pins={"joint":"8a9b38bb96df8f8b1a74b9a73e30dd692958de8d6b46d87011710630df89ce6d",
      "short":"6dd89d1fc89d74d955bad801b3742dff30ab4486caff791c85a47dfa14a12d3e"}
def save(p,data):
    p.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")

def run_panel(kind,label,selected=cases):
    diag=kind!="timed"
    binaries={role:(CACHE/(role+"-diag")/"abc.exe" if diag else
              CACHE/"online/abc.exe" if role=="online" else
              REF/".local/variants"/("joint" if role=="joint" else "screen-short")/"abc.exe") for role in roles}
    hashes={k:sha(v) for k,v in binaries.items()}
    if not diag: assert all(hashes[k]==v for k,v in pins.items())
    commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    dest=D/"results"/label
    dest.mkdir(parents=True,exist_ok=False)
    env={k:v for k,v in os.environ.items() if not k.startswith(("REPLAY_","RM_","OPTWIN_"))}
    env.update(REPLAY_RULES="both",REPLAY_BUDGET="1")
    if diag: env["REPLAY_STATS"]="1"
    if kind=="trace": env["REPLAY_TRACE"]="1"
    save(dest/"manifest.json",dict(commit=commit,binaries=hashes,cases=selected,kind=kind,
         methods=roles,timeout=300 if diag else 60,strict_bounds=truth_bounds,
         order="joint,short,online; then online,short,joint in timed panel",
         oracle_commit="5400328802c98c1870fb7f61ff2475f698ee48ea",
         guard_source="3705fbc086f28aedd996061f6c7a7d6f8d340632",host=os.environ.get("COMPUTERNAME")))
    # A pinned external controller reserves its lane even between consecutive solves.
    busy_since=time.time()
    while True:
        free=[c for c in cores() if not competitors(sum(1<<x for x in c),os.getpid())]
        if free: break
        time.sleep(15)
    physical=free[-1]
    mask=sum(1<<x for x in physical); cpu=physical[0]
    save(dest/"allocation.json",dict(physical=physical,cpu=cpu,wait_s=time.time()-busy_since,start=time.time()))
    watcher=subprocess.Popen([sys.executable,str(D/"guard.py"),str(dest),str(cpu),str(os.getpid())])
    try:
        pin(cpu)
        while not (dest/"guard.jsonl").exists():
            if watcher.poll() is not None: raise RuntimeError("guard failed")
            time.sleep(.05)
        for truth in selected:
            for i,role in enumerate(roles if diag else roles+roles[::-1],1):
                if watcher.poll() is not None or competitors(mask,os.getpid()):
                    raise RuntimeError("Physical core occupied; retain invalid panel")
                slot=dest/(truth+"-"+str(i)+"-"+role)
                child_env=dict(env)
                if diag and truth=="006b": child_env["RM_QUERY_PREFIX"]="1"
                result=run(binaries[role],truth,4,2,300 if diag else 60,slot,env=child_env,
                       metadata=dict(truth=truth,method=role,cpu=cpu,order=i,diagnostic=kind))
                path=slot/"solver.log"
                if diag and truth=="006b" and result["returncode"]==77:
                    if "DIAGNOSTIC_PREFIX" not in path.read_text(): raise RuntimeError(result)
                    save(slot/"prefix.json",dict(status="completed_query_prefix",optimality="unknown"))
                elif result["status"]!="timeout":
                    if result.get("witness",{}).get("activity")!=truth_bounds[truth]:
                        raise RuntimeError(("invalid optimum",slot,result))
                elif diag: raise RuntimeError(("incomplete diagnostic",slot))
                if diag:
                    gz=slot/"solver.log.gz"
                    with path.open("rb") as source,gzip.open(gz,"wb") as target: shutil.copyfileobj(source,target)
                    if kind=="trace": save(slot/"audit.json",check(gz,role))
                    else:
                        with gzip.open(gz,"rt") as inp:
                            save(slot/"profile.json",[list(map(int,l.split()[1:])) for l in inp if l.startswith("WORK ")])
                    path.unlink()
                print(kind,truth,i,role,result["status"],round(result["wall_s"],3),flush=True)
        time.sleep(.25)
    finally:
        (dest/"guard.stop").touch()
        watcher.wait(timeout=10)
    rows=list(map(json.loads,(dest/"guard.jsonl").read_text().splitlines()))
    assert len(rows)>1 and not any(x["foreign"] for x in rows),"competing timing process observed"
    save(dest/"complete.json",dict(samples=len(rows),observed_overlap=0,
         max_sample_gap_s=max(b["t"]-a["t"] for a,b in zip(rows,rows[1:]))))
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("kind",choices=["trace","profile","timed"])
    p.add_argument("label")
    p.add_argument("--only",choices=cases)
    a=p.parse_args()
    run_panel(a.kind,a.label,(a.only,) if a.only else cases)
