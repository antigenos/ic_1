"""Compare a separately implemented cost-ordered search to the constructive library and old sublevels."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import time

from library import HERE, family, pin


def validate(data):
    proof = data["cap"]
    cases = family()
    assert list(data["optima"]) == cases
    observed = [(c,n,count) for c,n,count in data["state_counts"]]
    assert observed == sorted(observed) and len({(c,n) for c,n,_ in observed}) == len(observed)
    assert all(0 <= c <= proof-30 and 0 <= n <= c//30 and count>0 for c,n,count in observed)
    evidence = HERE/"evidence"
    reference = json.loads((evidence/"leaves-690.json").read_text())
    for row in reference["circuits"]:
        expected = row["activity"] if row["activity"] <= proof else -1
        assert data["optima"][row["truth"]]==expected,(row, data["optima"][row["truth"]])
    old = json.loads((evidence/"orbit-oracle.json").read_text())["results"]
    levels = {int(budget): result["states_by_depth"] for budget,result in old.items()}
    for name in ("library-540","library-600","leaves-660"):
        item=json.loads((evidence/(name+".json")).read_text())
        bound=item["cap"]-30 if item.get("terminal") else item["cap"]
        levels[bound]=item["states_by_depth"]
    checked=[]
    for bound, expected in sorted(levels.items()):
        if bound > proof-30:
            continue
        counts=Counter()
        for cost,depth,number in observed:
            if cost<=bound:
                counts[depth]+=number
        assert [counts[n] for n in range(max(counts)+1)]==expected,(bound,counts,expected)
        checked.append(bound)
    for budget,result in old.items():
        if int(budget)>proof: continue
        for t, v in data["optima"].items():
            assert result["optima"][t] == (v if 0<=v<=int(budget) else -1)
    return dict(matched_classes=len(cases),exact_within_cap=sum(v>=0 for v in data["optima"].values()),
                earlier_state_sublevels_matched=checked,stored_states=sum(count for _,_,count in observed))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("output",type=Path)
    p.add_argument("--binary",type=Path)
    p.add_argument("--cap",type=int,default=662)
    p.add_argument("--cpu",type=int,default=24)
    a=p.parse_args()
    if a.binary:
        if a.output.exists(): raise FileExistsError(a.output)
        pin(a.cpu)
        binary=a.binary.resolve(strict=True)
        start=time.perf_counter()
        r=subprocess.run([str(binary),str(a.cap)],input="\n".join(family()),capture_output=True,text=True,check=True)
        duration=time.perf_counter()-start
        states=[]
        optima={}
        for line in r.stdout.splitlines():
            fields=line.split()
            if fields[0]=="states": states.append(list(map(int,fields[1:])))
            else:
                assert fields[0]=="opt" and len(fields)==3
                target=f"{int(fields[1],16):04x}"
                assert target not in optima
                optima[target]=int(fields[2])
        data=dict(cap=a.cap,cpu=a.cpu,cold_wall_s=duration,
                  binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),state_counts=states,optima=optima)
        data["audit"]=validate(data)
        a.output.write_text(json.dumps(data,separators=(",",":"))+"\n",encoding="utf-8")
    else:
        data=json.loads(a.output.read_text())
        assert data["audit"]==validate(data)
    print(json.dumps(data["audit"]),round(data["cold_wall_s"],3))
