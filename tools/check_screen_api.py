"""Differentially check existential and forced-XOR fast paths against the pinned core."""
import ctypes as C
from collections import Counter
import json
import os
from pathlib import Path
import random
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def run():
    dest=ROOT/".local/screen-api-qa"
    dest.mkdir(exist_ok=True)
    (dest/"check.c").write_text('''#include <string.h>
#include "screen_exists_core.h"
#include "screen_support.h"
int check(unsigned n,unsigned t,unsigned ops,unsigned *z,unsigned *o,unsigned *d,int cap,unsigned ch){
    P9JointResult expected,actual;
    if(p9_joint_support(n,t,ops,z,o,d,cap,ch,&expected)) return -1;
    int found=ScreenExists(n,t,ops,z,o,d,NULL,NULL,cap,ch&1,(ch>>1)&1);
    if(found!=(expected.supported[0]!=0)) return -2;
    if(screen_support(n,t,ops,z,o,d,cap,ch,&actual) || memcmp(&actual,&expected,sizeof(actual))) return -3;
    return found;
}
''')
    subprocess.run(["gcc","-O2","-std=gnu11","-shared","-I../../tools","-I../reference/src",
                    "-I../variants/screen-exists","check.c","../reference/src/joint_relation.c",
                    "-o","check.so"],cwd=dest,check=True)
    handle=os.add_dll_directory(str(Path(shutil.which("gcc")).parent)) if os.name=="nt" else None
    lib=C.CDLL(str(dest/"check.so"))
    lib.check.argtypes=[C.c_uint]*3+[C.POINTER(C.c_uint)]*3+[C.c_int,C.c_uint]
    rng=random.Random(20261121)
    counts=Counter()
    for n in (4,8,16):
        full=(1<<n)-1
        for i in range(2000):
            side=i%2
            pin=sum((r>>(i%(n.bit_length()-1))&1)<<r for r in range(n))
            g=rng.randrange(1,1<<(n-1))*2
            t=(g^pin) if i%3 else rng.randrange(1<<(n-1))*2
            known=rng.randrange(1<<n)|1
            z=[0,0]; o=[0,0]; d=[0,0]
            z[side]=known&~g; o[side]=known&g
            z[1-side]=full^pin; o[1-side]=pin
            d[side]=(rng.randrange(1<<(n//2))<<1) if i%4 else (1<<(n//2+1))-2
            d[1-side]=1<<(n//2)
            cap=rng.randrange(-1,260)
            ops=rng.randrange(32) if i%2 else 31
            rc=lib.check(n,t,ops,(C.c_uint*2)(*z),(C.c_uint*2)(*o),(C.c_uint*2)(*d),cap,1<<side)
            assert rc>=0,(n,i,rc)
            counts["feasible" if rc else "infeasible"]+=1
    if handle:
        handle.close()
    return dict(seed=20261121, total=sum(counts.values()), verdicts=counts, disagreements=0)


if __name__=="__main__":
    print(json.dumps(run(),indent=2))
