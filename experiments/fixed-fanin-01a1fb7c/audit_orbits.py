"""Validate the independent orbit enumeration against known complete sublevel sets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]/"tools"))
from repeat_0189 import pin


def validate(binary, cpu, output):
    pin(cpu)
    with ZipFile(HERE/"reproduction.zip") as archive:
        cases = json.loads(archive.read("evidence/e14-main/manifest.json"))["cases"]
        records = [json.loads(line) for arm in ("author","support","both")
                   for line in archive.read(f"evidence/e14-main/{arm}.jsonl").splitlines()]
    bounded = json.loads((HERE/"evidence/bounded-oracle.json").read_text())["checks"]
    tail = json.loads((HERE/"evidence/tail-oracle.json").read_text())["cases"]
    known = {r["witness"]["truth"]:r["witness"]["activity"] for r in records if "witness" in r}
    for t in ("0016", "0017"):
        proof=json.loads((HERE/"evidence"/f"strict-{t}.json").read_text())
        assert not proof["cheaper_exists"]
        known[t]=proof["strict_upper"]
    report = dict(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),cpu=cpu,results={})
    for cap in (240,360,480):
        start = time.perf_counter()
        proc = subprocess.run([str(binary.resolve()),str(cap)], text=True, input="\n".join(cases),
                              capture_output=True, check=True)
        elapsed = time.perf_counter()-start
        first, *items = proc.stdout.splitlines()
        tag,*counts = first.split()
        assert tag=="layers" and counts[0]=="1"
        values = {f"{int(t,16):04x}":int(x) for t,x in (line.split() for line in items)}
        assert list(values)==cases
        if cap in (240,360):
            oracle = bounded if cap==240 else tail
            full = {r["truth"]:r["cost"] for r in oracle if r["cap"]==cap and r["projected"]==0}
            assert full==values
        for t, score in known.items():
            assert values[t]==(score if score<=cap else -1), (cap,t,score,values[t])
        report["results"][cap]=dict(seconds=elapsed,states_by_depth=list(map(int,counts)),
                                    certified=sum(v>=0 for v in values.values()),optima=values)
        output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print(cap,sum(map(int,counts)),report["results"][cap]["certified"],round(elapsed,3),flush=True)


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("binary",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--cpu",type=int,required=True)
    args=p.parse_args()
    validate(args.binary,args.cpu,args.output)
