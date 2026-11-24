"""Re-read raw witnesses, query traces and actual allocation records of the delivered panels."""
import gzip, json, sys, hashlib
from pathlib import Path
from audit import check
from report import read, summarize
from witness import simulate

def verify(r):
    folders=[r/k for k in ("paired-01","audit-01","profile-02")]
    totals={}
    for folder in folders:
        manifest=read(folder/"manifest.json")
        alloc=read(folder/"allocation.json")
        samples=[json.loads(s) for s in (folder/"guard.jsonl").read_text().splitlines()]
        assert samples and all(s["physical"]==alloc["physical"] and not s["foreign"] for s in samples)
        assert len(samples)==read(folder/"complete.json")["samples"]
        expected_runs=24 if manifest["kind"]=="timed" else 12
        paths=sorted(folder.glob("*/result.json"))
        assert len(paths)==expected_runs
        for p in paths:
            rec=read(p); slot=p.parent; t,i,role=slot.name.split("-")
            request=read(slot/"request.json")
            assert role==manifest["methods"][((int(i)-1) if int(i)<=3 else 6-int(i))]
            assert request["binary_sha256"]==rec["binary_sha256"]==manifest["binaries"][role]
            assert rec["child_affinity"]==read(slot/"launch.json")["child_affinity"]==[alloc["cpu"]]
            assert rec["command"]==["abc.exe","-c","pexact -I 4 -M 2 "+t]
            assert rec["timeout_s"]==manifest["timeout"]
            if manifest["kind"]=="timed":
                text=(slot/"solver.log").read_text(errors="strict")
                assert not any(x.startswith(("WORK ","CLASH ","REASON ","JOINT ")) for x in text.splitlines())
            else:
                text=gzip.open(slot/"solver.log.gz","rt").read()
            if rec["status"]=="timeout":
                assert rec["capped_wall_s"]==manifest["timeout"] and "witness" not in rec
            elif (slot/"prefix.json").exists():
                assert rec["returncode"]==77 and "DIAGNOSTIC_PREFIX" in text and "witness" not in rec
            else:
                assert rec["returncode"]==0 and rec["status"]=="solver_completed_verified_witness"
                assert simulate(text,4,int(t,16))==rec["witness"]
                assert rec["witness"]["activity"]==manifest["strict_bounds"][t]
            if manifest["kind"]=="trace":
                fresh=json.loads(json.dumps(check(slot/"solver.log.gz",role)))
                assert fresh==read(slot/"audit.json")
        totals[folder.name]=expected_runs
    summary=summarize(*folders)
    # Terminated diagnostics are always distinct from the formal run population.
    return dict(panels=totals,summary=summary)

if __name__=="__main__":
    data=verify(Path(__file__).resolve().parent/"results")
    print(json.dumps(data,indent=2))
