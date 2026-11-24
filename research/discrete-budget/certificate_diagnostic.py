"""Estimate the number of useful minimum-sum certificates on development snapshots only."""
import json
from collections import Counter,defaultdict
from build import ROOT,gitfile


def weight(a):
    return 2*a*(16-a)


def min_charge(mask):
    return weight((mask&-mask).bit_length()-1)


def main():
    outer={}
    for line in gitfile("evidence/filtered-0189/solver.log").decode().splitlines():
        if line.startswith("WINDOW "):
            d=dict(x.split("=") for x in line.split()[1:])
            key=tuple(int(d[k]) for k in ("r","lo","hi"))
            assert key not in outer or outer[key]==d["state"]
            outer[key]=d["state"]
    result=defaultdict(Counter)
    for line in (ROOT/"evidence/screen-window-snapshots/solver.log").read_text().splitlines():
        if not line.startswith("WINDOW "):
            continue
        target,gates,lo,hi,j,k,opened,ops,sx,sy=map(int,line.split()[1:11])
        if not sx:
            assert not sy
            continue
        dom=[int(token.split(",")[2]) for token in line.split()[11:]]
        n=sum(min_charge(m) for i,m in enumerate(dom) if i>=4 and i not in (j,k))
        min_pair=sum(min_charge(s) for i,s in ((j,sx),(k,sy)) if i>=4)
        label="skipped" if outer[gates-1,lo,hi]=="skip" else "entered"
        result[label]["eligible"]+=1
        result[label]["minimum_certifies_all"]+=n+min_pair>=lo
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
