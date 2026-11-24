"""Audit published emitted clauses, labeling the outer query key from a separate historical run."""
import gzip
import hashlib
import json
from collections import Counter,defaultdict
from build import ROOT,gitfile
from audit import classify


def main():
    states=defaultdict(set)
    for line in gitfile("evidence/filtered-0189/solver.log").decode().splitlines():
        if line.startswith("WINDOW "):
            data=dict(p.split("=") for p in line.split()[1:])
            states[int(data["r"]),int(data["lo"]),int(data["hi"])].add(data["state"])
    expected=json.loads((ROOT/"evidence/screen-budget-audit.json").read_text())
    summary={}
    for mode in ("interval","holes"):
        raw=gzip.decompress((ROOT/"evidence/screen-traces"/(mode+"-0189.log.gz")).read_bytes())
        assert hashlib.sha256(raw).hexdigest()==expected[mode]["raw_sha256"]
        counts,all_victims=Counter(),Counter()
        examples={}
        for line in raw.decode().splitlines():
            if line.startswith("WINDOW_BOUND "):
                _,lo,hi=line.split()
            elif line.startswith("REASON "):
                r=int(line.split()[2])-1
                key=(r,int(lo),int(hi))
                historical=states[key]
                label=("unmatched" if not historical else "mixed" if len(historical)>1
                       else "skipped" if historical=={"skip"} else "entered")
                tier,victim=classify(line,int(lo),int(hi),mode)
                name="/".join((label,tier,victim))
                counts[name]+=1
                all_victims[victim]+=1
                examples.setdefault(name,dict(r=r,L=int(lo),H=int(hi),clause=line))
        assert all_victims==expected[mode]["verified"]
        summary[mode]=dict(counts=counts,examples=examples)
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    main()
