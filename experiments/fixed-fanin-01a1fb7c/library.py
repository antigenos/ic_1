"""Materialize and independently replay every certified four-input library circuit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from zipfile import ZipFile

HERE=Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]/"tools"))
from repeat_0189 import pin
from witness import simulate


def replay(row):
    target=int(row["truth"],16)
    assert row["activity"] >= 0 and row["direct"]==-2 and row["complement"]==(target & 1)
    gates=row["gates"]
    lines=[f"Realization of given 4-input function using {len(gates)} two-input gates complementary={row['complement']}:"]
    def name(i):
        return chr(97+i) if i<4 else f"{i:02}"
    for i,(hi,lo,op) in enumerate(gates,4):
        assert 0<=lo<hi<i and op in (2,4,6,8,14)
        if i==3+len(gates) and row["complement"]:
            op ^= 15
        lines.append(f"{i:02} = 4'b{op:04b}( {name(hi)} {name(lo)} )")
    lines.append(f"Switching Activity={row['activity']}")
    result=simulate("\n".join(lines),4,target)
    assert result["truth"]==row["truth"] and result["activity"]==row["activity"]


def family():
    with ZipFile(HERE/"reproduction.zip") as archive:
        return json.loads(archive.read("evidence/e14-main/manifest.json"))["cases"]


def check(data, previous=None):
    cases=family()
    assert [r["truth"] for r in data["circuits"]]==cases
    frozen=json.loads((HERE/"evidence/orbit-oracle.json").read_text())["results"]["480"]["optima"]
    prior={r["truth"]:r["activity"] for r in previous["circuits"]} if previous else {}
    for row in data["circuits"]:
        t,activity=row["truth"],row["activity"]
        if frozen[t]>=0 or data["cap"]==480:
            assert activity==frozen[t]
        if prior.get(t,-1)>=0:
            assert prior[t]==activity
        if activity<0:
            assert activity==-1 and not row["gates"]
        else:
            assert activity <= data["cap"]
            replay(row)
    return sum(r["activity"]>=0 for r in data["circuits"])


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("output",type=Path)
    p.add_argument("--binary",type=Path)
    p.add_argument("--cap",type=int,default=480)
    p.add_argument("--cpu",type=int,default=24)
    p.add_argument("--previous",type=Path)
    args=p.parse_args()
    prev=json.loads(args.previous.read_text()) if args.previous else None
    if args.binary:
        if args.output.exists(): raise FileExistsError(args.output)
        pin(args.cpu)
        binary=args.binary.resolve()
        start=time.perf_counter()
        result=subprocess.run([str(binary),str(args.cap),"--circuits"],input="\n".join(family()),
                              capture_output=True,text=True,check=True)
        elapsed=time.perf_counter()-start
        first,*lines=result.stdout.splitlines()
        tag,*layers=first.split()
        assert tag=="layers" and layers[0]=="1"
        data=dict(cap=args.cap,cpu=args.cpu,cold_wall_s=elapsed,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  states_by_depth=list(map(int,layers)),circuits=list(map(json.loads,lines)))
        data["verified"]=check(data,prev)
        args.output.write_text(json.dumps(data,ensure_ascii=True,separators=(",",":"))+"\n",encoding="utf-8")
    else:
        data=json.loads(args.output.read_text())
        assert data["verified"]==check(data,prev)
    print(data["cap"],data["verified"],sum(data["states_by_depth"]),round(data["cold_wall_s"],3))
