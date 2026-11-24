"""Intersect historical fixed points with independently archived, outer-filtered query keys."""
from collections import defaultdict,Counter
import json
from pathlib import Path
import sys
from build import HERE,ROOT,gitfile
sys.path.insert(0,str(ROOT/"tools"))
from screen_cost_window import measure


def main():
    groups=defaultdict(set)
    for line in gitfile("evidence/filtered-0189/solver.log").decode().splitlines():
        if line.startswith("WINDOW "):
            d=dict(v.split("=") for v in line.split()[1:])
            groups[(int(d["r"]),int(d["lo"]),int(d["hi"]))].add(d["state"])
    blocks=defaultdict(list)
    for line in (ROOT/"evidence/screen-window-snapshots/solver.log").read_text().splitlines():
        if line.startswith("WINDOW "):
            _,nodes,lo,hi,_,_,opened=map(int,line.split()[1:8])
            key=(nodes-1,lo,hi)
            states=groups[key]
            assert len(states)==1,(key,states)
            state=next(iter(states))
            assert state in ("skip","1","-1")
            timing="skipped" if state=="skip" else "entered"
            kind="count" if opened==-1 else "connection"
            blocks[(timing,kind)].append(line)
    summary={}
    combined=Counter()
    for key,lines in blocks.items():
        path=HERE/".local"/("historical-"+"-".join(key)+".log")
        path.write_text("\n".join(lines))
        res=measure(path)
        summary["-".join(key)]=res
        combined.update(res["counts"])
    expected=json.loads((ROOT/"evidence/screen-window-results.json").read_text())["counts"]
    assert dict(combined)==expected
    print(json.dumps(dict(total=combined,by_outer_status_and_victim=summary),indent=2))


if __name__=="__main__":
    main()
