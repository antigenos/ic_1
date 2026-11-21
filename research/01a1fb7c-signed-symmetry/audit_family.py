"""Differentially reconstruct every filter clause over the surveyed exact-synthesis family."""
from collections import Counter
from functools import cache
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from check_order import KEYS, swaps
from check_symmetry import HERE, FIRST, OPS, PINS, gate, stabilizer, transform


@cache
def blockers(target, mode):
    group = [m for phase,m in stabilizer(target) if mode!="unsigned" or not phase]
    key = KEYS.__getitem__ if mode in ("ordered","combined") else int
    return {h for h in FIRST if any(key(transform(h,m)) < key(h) for m in group)}


def expected(target,n,mode):
    loc = 1+3*n
    sel = {}
    for obj in range(4,4+n):
        for pin in range(2):
            for signal in range(obj-pin):
                sel[obj,pin,signal] = loc
                loc += 1
    cases = []
    if mode in ("first-use","combined"):
        for left,right in swaps(target):
            for obj in range(4,4+n):
                for pin in range(2):
                    if (obj,pin,right) not in sel:
                        continue
                    anti = 2*sel[obj,pin,right]+1
                    literals = [2*v for (gate_no,side,signal),v in sel.items() if signal==left
                                and (gate_no<obj or (gate_no==obj and side!=pin))]
                    cases.append(tuple(sorted([anti,*literals])))
    if mode not in ("first-use","off"):
        suppressed = blockers(target,mode)
        for hi in range(1,4):
            for lo in range(hi):
                for op in OPS:
                    if gate(op,PINS[lo],PINS[hi]) not in suppressed:
                        continue
                    bits = [2*i+(op>>i & 1) for i in range(1,4)]
                    cases.append(tuple(sorted([2*sel[4,0,hi]+1,2*sel[4,1,lo]+1,*bits])))
    return Counter(cases)


def main():
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        truths = [int(t,16) for t in json.loads(z.read("evidence/npn-family.json"))["essential"]]
        sizes = {int(json.loads(row)["witness"]["gates"]) for row in
                 z.read("evidence/e14-main/both.jsonl").splitlines() if "witness" in json.loads(row)}
    queries = [(t,n) for t in truths for n in sorted(sizes|{2,10})]
    stream = "".join(f"{t:04x} {n}\n" for t,n in queries)
    stats = {}
    with TemporaryDirectory() as tmp:
        binary = Path(tmp)/("check.exe" if os.name=="nt" else "check")
        subprocess.run(["gcc","-std=c11","-O2",str(HERE/"emit_clauses.c"),"-o",str(binary)],check=True)
        for mode in ("off","unsigned","signed","first-use","ordered","combined"):
            env = {k:v for k,v in os.environ.items() if not k.startswith("REPLAY_FIRST")}
            env["REPLAY_FIRST_SYMMETRY"] = mode
            trace = subprocess.check_output([str(binary)],input=stream,text=True,env=env)
            count = 0
            blocks = trace.lstrip("Q ").split("\nQ ")
            assert len(blocks)==len(queries)
            for key,block in zip(queries,blocks):
                head,*raw = block.splitlines()
                t,n = head.split()
                assert (int(t,16),int(n))==key
                observed = Counter(tuple(sorted(map(int,line.split()[1:]))) for line in raw)
                assert observed==expected(*key,mode), (key,mode,observed-expected(*key,mode))
                count += observed.total()
            stats[mode] = count
    return dict(functions=len(truths),gate_counts=sorted(sizes|{2,10}),queries_per_mode=len(queries),
                matched_clauses_by_mode=stats)


if __name__=="__main__":
    print(json.dumps(main(),indent=2))
