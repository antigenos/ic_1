"""Compare the compiled skip predicate with enumeration over raw gate populations."""
import ctypes
from itertools import product
import json
import os
from pathlib import Path
import random
import subprocess

HERE = Path(__file__).resolve().parent


def check():
    dest = HERE / ".local/check"
    dest.mkdir(parents=True, exist_ok=True)
    stub = dest / "check.c"
    stub.write_text('''#include <string.h>
#include <stdlib.h>
#define MAJ_NOBJS 32
#include "window_proof.h"
static WindowProof w;
void init(int n,int m) { window_init(&w,n); w.mode=m; }
void reject(int r,int a,int b) { window_unsat(&w,r,a,b); }
int skip(int r,int a,int b) { return window_skip(&w,r,a,b); }
''')
    so = dest / ("check.dll" if os.name == "nt" else "check.so")
    subprocess.run(["gcc","-O2","-shared","-fPIC","-I","../..",stub.name,"-o",so.name], cwd=dest, check=True)
    c = ctypes.CDLL(str(so))
    rng = random.Random(9720)
    tests = 0
    for n in (2,3,4):
        rows = 2**n
        allowed = {}
        for r in range(1,5):
            populations = [range(2**max(n-i-2,0), rows//2+1, 2**max(n-i-2,0)) for i in range(r)]
            allowed[r] = {sum(2*a*(rows-a) for a in choices) for choices in product(*populations)}
        for mode in range(4):
            c.init(n,mode)
            proved = {r:set() for r in allowed}
            real = {r:{s for s in allowed[r] if rng.random()<0.18} for r in allowed}
            for it in range(12000):
                r = rng.randint(1,4)
                lo = rng.randint(0,r*rows*rows//2+8)
                hi = lo + rng.choice((0,1,2,3,4,13,29,75))
                even = set(range(lo+(lo%2), hi+1, 2))
                candidate = even & allowed[r] if mode & 1 else even
                remaining = candidate - proved[r] if mode & 2 else candidate
                answer = bool(c.skip(r,lo,hi))
                assert answer == (bool(mode) and not remaining), (n,r,lo,hi,mode)
                assert not (answer and real[r] & even)
                if not real[r] & even and rng.random()<0.25:
                    proved[r].update(even)
                    c.reject(r,lo,hi)
                tests += 1
    return dict(seed=9720, input_counts=[2,3,4], charged_gates=[1,2,3,4], modes=4,
                sequential_queries=tests, disagreements=0, incorrectly_rejected_witnesses=0)


if __name__ == "__main__":
    print(json.dumps(check(),indent=2))
