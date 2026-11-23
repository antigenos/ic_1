"""Recompute paired outcomes, raw evidence hashes and witness values."""
import argparse
from datetime import datetime
from hashlib import sha256
import json
from math import exp, log
from pathlib import Path
from statistics import mean
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"tools"))
from witness import simulate


def audit(manifest, rows, expected):
    by_case={}
    hashes={}
    for row in rows:
        meta=row["experiment"]
        t,arm=meta["truth"],meta["arm"]
        assert (t,arm) not in by_case and arm in "AB"
        assert row["binary_sha256"] == hashes.setdefault(arm,row["binary_sha256"])
        assert row["child_affinity"]==[meta["cpu"]]
        assert row["wall_s"]<=row["timeout_s"]+3
        assert abs(row["capped_wall_s"]-min(row["wall_s"],row["timeout_s"]))<1e-6
        raw=row["solver_output"].encode()
        assert sha256(raw).hexdigest()==row["solver_log_sha256"]
        if row["status"]=="solver_completed_verified_witness":
            assert row["returncode"]==0
            witness=simulate(raw.decode(),4,int(t,16))
            assert witness==row["witness"] and (t not in expected or witness["activity"]==expected[t])
        else:
            assert row["status"]=="timeout" and row["wall_s"]>=row["timeout_s"]-0.15
        by_case[t,arm]=row
    by_arm={a:{"completed":0,"capped_s":0.0} for a in "AB"}
    ratios={}
    only={a:[] for a in "AB"}
    assert len(by_case)==2*len(manifest)
    for case in manifest:
        t=case["truth"]
        a,b=(by_case[t,key] for key in "AB")
        for arm,row in (("A",a),("B",b)):
            assert row["experiment"]["cpu"]==case["cpu"]
            assert row["experiment"]["order"]==1+case["order"].index(arm)
            by_arm[arm]["completed"]+=int("witness" in row)
            by_arm[arm]["capped_s"]+=row["capped_wall_s"]
        if "witness" in a and "witness" in b:
            assert a["witness"]["activity"]==b["witness"]["activity"]
            ratios[t]=a["wall_s"]/b["wall_s"]
        elif "witness" in a or "witness" in b:
            only["A" if "witness" in a else "B"].append(t)
    return dict(cases=len(manifest),arms=by_arm,common=len(ratios),
                paired_geomean=exp(mean(map(log,ratios.values()))) if ratios else None,
                only=only,ratios=ratios,slower=[t for t,v in ratios.items() if v<1],
                verified_resimulations=sum(d["completed"] for d in by_arm.values()),binary_sha256=hashes)


def historical():
    costs={}
    for arm in ("both","author","support"):
        path=HERE/f"reproduction/evidence/e14-main/{arm}.jsonl"
        for line in path.read_text().splitlines():
            row=json.loads(line)
            if "witness" in row:
                t=row["experiment"]["truth"]
                assert costs.setdefault(t,row["witness"]["activity"])==row["witness"]["activity"]
    return costs


def read_raw(root):
    rows=[]
    for path in sorted(root.glob("*/*/result.json")):
        row=json.loads(path.read_text())
        raw=path.with_name("solver.log").read_bytes()
        row.update(solver_output=raw.decode(),solver_log_sha256=sha256(raw).hexdigest())
        if (root/"configuration.json").exists():
            for name in ("request","launch","accepted"):
                row[name]=json.loads(path.with_name(f"{name}.json").read_text())
        rows.append(row)
    return rows


def audit_full(manifest, rows, conf):
    from check_orbits import check_witness, first_gate_truth, representatives
    family=json.loads((HERE/"reproduction/evidence/npn-family.json").read_text())["essential"]
    cpus=list(range(16,32,2))
    assert conf["cap"]==300 and conf["cpus"]==cpus and len(family)==len(set(family))==208
    expected=[dict(truth=t,cpu=cpus[i%8],order="AB" if (i//8+i%8)%2==0 else "BA")
              for i,t in enumerate(family)]
    assert manifest==expected
    by_key={(r["experiment"]["truth"],r["experiment"]["arm"]):r for r in rows}
    assert len(rows)==len(by_key)==416
    last_end={}
    max_skew=0
    first_gates={a:{"witnesses":0,"canonical":0,"checked_images":0} for a in "AB"}
    for case in manifest:
        truth,cpu=case["truth"],case["cpu"]
        for pos,arm in enumerate(case["order"],1):
            r=by_key[truth,arm]
            meta=dict(cpu=cpu,truth=truth,arm=arm,order=pos)
            assert r["experiment"]==meta and r["binary_sha256"]==conf["binaries"][arm]
            cmd=r["command"]
            assert cmd[0] in ("abc.exe","abc") and cmd[1:]==["-c",f"pexact -I 4 -M 2 {truth}"]
            assert r["timeout_s"]==300 and r["launch"]==dict(pid=r["pid"],child_affinity=[cpu])
            assert r["request"]=={k:r[k] for k in ("experiment","timeout_s","start_utc","binary_sha256","command")}
            times=r["accepted"]
            elapsed,awake=times["utc_elapsed"],times["awake_elapsed"]
            skew=abs(elapsed-awake)
            assert times["valid"] is True and skew<5 and r["wall_s"]>0
            assert awake>0 and elapsed>=r["wall_s"]-0.1 and elapsed<=r["wall_s"]+5
            assert ("witness" in r)==(r["status"]=="solver_completed_verified_witness")
            if r["status"]=="solver_completed_verified_witness":
                assert "Total runtime" in r["solver_output"]
                target=int(truth,16)
                h=first_gate_truth(r["solver_output"])
                canonical=h in representatives(4,target)
                assert arm!="B" or canonical, (truth,"noncanonical first gate",h)
                first_gates[arm]["witnesses"]+=1
                first_gates[arm]["canonical"]+=int(canonical)
                first_gates[arm]["checked_images"]+=check_witness(
                    r["solver_output"],target,r["witness"]["activity"])
            start=datetime.fromisoformat(r["start_utc"])
            assert start.utcoffset() is not None
            epoch=start.timestamp()
            assert epoch>=last_end.get(cpu,0)-0.1
            last_end[cpu]=epoch+r["wall_s"]
            max_skew=max(max_skew,skew)
    return dict(accepted=len(rows),cpu_lanes=len(cpus),cap_s=conf["cap"],
                max_wall_awake_gap_s=max_skew,first_gates=first_gates)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("dir",type=Path)
    p.add_argument("--export",type=Path)
    p.add_argument("--full",action="store_true",help="require the complete 208-class, 300-second protocol")
    args=p.parse_args()
    manifest=json.loads((args.dir/"manifest.json").read_text())
    recorded=args.dir/"runs.jsonl"
    rows=([json.loads(s) for s in recorded.read_text().splitlines()] if recorded.exists()
          else read_raw(args.dir))
    report=audit(manifest,rows,historical())
    config_path=args.dir/"configuration.json"
    if args.full or config_path.is_file():
        report["protocol"]=audit_full(manifest,rows,json.loads(config_path.read_bytes()))
    if recorded.is_file() and (args.dir/"summary.json").is_file():
        assert json.loads((args.dir/"summary.json").read_bytes())==report, "Published summary differs from replay"
    if args.export:
        args.export.mkdir(parents=True,exist_ok=False)
        (args.export/"manifest.json").write_bytes((args.dir/"manifest.json").read_bytes())
        if config_path.exists():
            (args.export/"configuration.json").write_bytes(config_path.read_bytes())
        (args.export/"runs.jsonl").write_bytes(("".join(json.dumps(r,separators=(",",":"))+"\n" for r in rows)).encode())
        (args.export/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
