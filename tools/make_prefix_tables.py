"""Build reusable low-dimensional cost tables without access to benchmark targets."""
import argparse
import hashlib
from itertools import combinations
import json
from pathlib import Path
import time

from probe_prefix_budget import PINS, activity, projections, restricted_optima


def gates(pins):
    for lo,hi in combinations(range(len(pins)),2):
        a,b=pins[hi],pins[lo]
        for code,h in zip((2,4,6,8,14),(a&~b,b&~a,a^b,a&b,a|b)):
            yield (hi,lo,code),h


def generate(dest):
    start=time.perf_counter()
    index, patterns = {}, []
    free = {0,0xaa,0xcc,0xf0}
    for gate1,h in gates(PINS):
        for gate2,g in gates((*PINS,h)):
            if g==0:
                continue
            ids=[]
            for u,v in zip(projections(h),projections(g)):
                extra=tuple(sorted({u,v}-free))
                ids.append(index.setdefault(extra,len(index)))
            patterns.append((*gate1,*gate2,activity(h,16)+activity(g,16),ids))
    assert len(index)<=256
    with dest.open("w",encoding="ascii",newline="\n") as f:
        f.write("/* Generated from all legal nonconstant two-gate prefixes. */\n")
        f.write("static const unsigned char prefix_opt[2][][128] = {\n".replace("[2][]",f"[2][{len(index)}]"))
        for mu in (0,20):
            f.write("{\n")
            for key in index:
                table=restricted_optima(key,mu)
                assert all(v%4==0 for v in table.values())
                f.write("{"+",".join(str(table[x]//4) for x in range(0,256,2))+"},\n")
            f.write("},\n")
        f.write("};\nstatic const struct { unsigned char hi,lo,op,hi2,lo2,op2; unsigned short cost; unsigned char id[20]; } prefix_patterns[] = {\n")
        for *desc,ids in patterns:
            f.write("{"+",".join(map(str,desc))+",{"+",".join(map(str,ids))+"}},\n")
        f.write("};\n")
    return dict(patterns=len(patterns), extras=len(index), bytes=dest.stat().st_size,
                sha256=hashlib.sha256(dest.read_bytes()).hexdigest(), generation_s=time.perf_counter()-start)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("header",type=Path)
    print(json.dumps(generate(p.parse_args().header),indent=2))
