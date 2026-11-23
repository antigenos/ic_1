"""Run and replay the preregistered comparison of signed and unsigned input changes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time

from compare_orbits import HERE, ROOT
from check_orbits import first_gate_truth, representatives
from audit_pairs import historical
from full import awake, lock, request_awake
from witness import simulate


def plan():
    family=json.loads((HERE/"orbit-check.json").read_bytes())["family"]
    panel=json.loads((HERE/"evidence/panel/manifest.json").read_bytes())
    exclude={r["truth"] for r in panel} | {"0189","0019","012d","6996","03dd","07f2","0017","018b"}
    history=(HERE/"reproduction/evidence/e14-main/both.jsonl").read_text().splitlines()
    pool=[]
    for line in history[104:]:
        row=json.loads(line)
        t=row["experiment"]["truth"]
        if t not in exclude and 2<=row["wall_s"]<45 and family[t]["signed"]<family[t]["plain"]:
            pool.append(t)
    pool.sort(key=lambda t:sha256(("orbit-phase-pairs-01a1fb7c/"+t).encode()).digest())
    assert pool==["069f","06f0","0696","19e6"]
    return [dict(truth=t,cpu=16+2*(i%2),order="BPPB" if i in (0,3,4) else "PBBP")
            for i,t in enumerate(["03dd","07f2",*pool])]


def load_case(root,case):
    observations=[]
    for i,arm in enumerate(case["order"],1):
        base=root/case["truth"]/f"{i}-{arm}"
        row=json.loads((base/"result.json").read_bytes())
        data=(base/"solver.log").read_bytes()
        row.update(solver_output=data.decode(),solver_log_sha256=sha256(data).hexdigest())
        observations.append(row)
    return observations


def check(cases,rows):
    assert len(rows)==4*len(cases)
    known=historical()
    hashes=set()
    report={}
    for j,case in enumerate(cases):
        t=case["truth"]
        sample=rows[j*4:j*4+4]
        times={a:[] for a in "BP"}
        values=set()
        for i,(arm,row) in enumerate(zip(case["order"],sample),1):
            assert row["experiment"]==dict(cpu=case["cpu"],truth=t,arm=arm,order=i)
            assert row["child_affinity"]==[case["cpu"]] and row["command"][1:]==["-c",f"pexact -I 4 -M 2 {t}"]
            assert row["timeout_s"]==60 and 0<row["wall_s"]<=63
            assert row["capped_wall_s"]==min(60,row["wall_s"])
            text=row["solver_output"]
            assert sha256(text.encode()).hexdigest()==row["solver_log_sha256"]
            if row["status"]=="solver_completed_verified_witness":
                assert row["returncode"]==0 and "Total runtime" in text
                w=simulate(text,4,int(t,16))
                assert w==row["witness"]
                assert first_gate_truth(text) in representatives(4,int(t,16),signed=arm=="B")
                values.add(w["activity"])
            else:
                assert row["status"]=="timeout" and row["wall_s"]>=59.85 and "witness" not in row
            times[arm].append(row["capped_wall_s"])
            hashes.add(row["binary_sha256"])
        assert len(values)<=1 and all(v==known[t] for v in values)
        complete={a:sum("witness" in r for r in sample if r["experiment"]["arm"]==a) for a in "BP"}
        report[t]=dict(capped_s=times,completed=complete,
                       paired_P_over_B=[p/b for p,b in zip(times["P"],times["B"])],
                       activity=next(iter(values),None))
    assert len(hashes)==1
    return dict(binary_sha256=hashes.pop(),cases=report)


def run_lanes(root,cases):
    root.mkdir(parents=True,exist_ok=True)
    def lane(cpu):
        for c in cases:
            if c["cpu"]!=cpu:
                continue
            dest=root/c["truth"]
            if dest.exists():
                # A partial case remains intact for explicit inspection on resumption.
                check([c],load_case(root,c))
                assert json.loads((dest/"clock.json").read_bytes())["valid"]
            else:
                before,up=time.time(),awake()
                subprocess.run([sys.executable,str(HERE/"compare_orbits.py"),c["truth"],str(dest),
                                "--cpu",str(cpu),"--order",c["order"],"--cap","60"],check=True)
                wall,active=time.time()-before,awake()-up
                clock=dict(utc_elapsed=wall,awake_elapsed=active,valid=abs(wall-active)<5)
                (dest/"clock.json").write_text(json.dumps(clock)+"\n")
                if not clock["valid"]:
                    raise ValueError(f"Clock discontinuity during {c['truth']}")
    with lock(root/"batch.lock"), request_awake(), ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lane,(16,18)))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run",action="store_true")
    p.add_argument("--data",type=Path)
    p.add_argument("--export",type=Path)
    args=p.parse_args()
    cases=plan()
    root=args.data or (ROOT/".local/orbit-phase-ablation" if args.run else HERE/"evidence/phase-ablation")
    if args.run:
        run_lanes(root,cases)
    packed=root/"runs.jsonl"
    if packed.is_file():
        assert json.loads((root/"manifest.json").read_bytes())==cases
        rows=[json.loads(line) for line in packed.read_text().splitlines()]
        clocks=json.loads((root/"clocks.json").read_bytes())
    else:
        rows=[r for case in cases for r in load_case(root,case)]
        clocks={c["truth"]:json.loads((root/c["truth"]/"clock.json").read_bytes()) for c in cases}
    for c in cases:
        clock=clocks[c["truth"]]
        assert clock["valid"] and abs(clock["utc_elapsed"]-clock["awake_elapsed"])<5
    report=check(cases,rows)
    if packed.is_file():
        assert json.loads((root/"summary.json").read_bytes())==report
    if args.export:
        args.export.mkdir(parents=True,exist_ok=False)
        (args.export/"manifest.json").write_text(json.dumps(cases,indent=2)+"\n")
        (args.export/"clocks.json").write_text(json.dumps(clocks,indent=2)+"\n")
        (args.export/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
        (args.export/"runs.jsonl").write_bytes("".join(json.dumps(r)+"\n" for r in rows).encode())
    print(json.dumps(report,indent=2))
