"""Reconstruct each emitted SAT clause, then find its weakest sufficient budget rule."""
from collections import Counter
import gzip
import json
from pathlib import Path
import sys
from build import HERE,ROOT
sys.path.insert(0,str(ROOT/"tools"))
from audit_trail import audit
from audit_screen_windows import reason


def classify(line,lo,hi,method):
    try:
        return "joint",audit(line)
    except AssertionError as e:
        if method=="joint" or not e.args or not isinstance(e.args[0],tuple) or e.args[0][0]!="satisfiable reason":
            raise
    try:
        return "interval",reason(line,lo,hi,False)
    except AssertionError as e:
        if method=="interval" or not e.args or not isinstance(e.args[0],tuple) or e.args[0][0]!=line:
            raise
    return "holes",reason(line,lo,hi,True)


def read_querylog(path):
    if path.suffix==".gz":
        with gzip.open(path,"rt") as f:
            yield from f
    else:
        with path.open() as f:
            yield from f


def assess(path,method):
    counts,printed,outer,cost,joint=Counter(),Counter(),Counter(),Counter(),Counter()
    per_width={}
    examples={}
    query=None
    total=0
    prefix=lambda line: dict(p.split("=") for p in line.split()[1:])
    for raw in read_querylog(path):
        line=raw.strip()
        if line.startswith("WINDOW_BOUND "):
            assert query is None
            _,lo,hi=line.split()
            query=(int(lo),int(hi))
        elif line.startswith("REASON "):
            assert query is not None and int(line.split()[4])==query[1]
            tier,victim=classify(line,*query,method)
            key=tier+"_"+victim
            counts[key]+=1
            total+=len(line.split())-8
            examples.setdefault(key,dict(line=line,window=query))
        elif line.startswith("COST "):
            data={k:int(v) for k,v in prefix(line).items()}
            width=data["hi"]-data["lo"]
            w=per_width.setdefault(width,Counter())
            for k,v in data.items():
                if k not in ("lo","hi","frequency"):
                    cost[k]+=v
                    w[k]+=v
            cost["frequency"]=data["frequency"]
        elif line.startswith("JOINT "):
            d=prefix(line)
            for k in ("checks","visits","counts","edges","conflicts"):
                joint[k]+=int(d[k])
            printed["sel"]+=int(d["edges"])
            printed["count"]+=int(d["counts"])
        elif line.startswith("WINDOW "):
            v=prefix(line)
            outer[v["state"]]+=1
            if v["state"] not in ("skip","build") and query is not None:
                assert query==(int(v["lo"]),int(v["hi"]))
                query=None
    assert query is None
    if path.suffix==".gz":
        assert {k:sum(c for key,c in counts.items() if key.endswith("_"+k)) for k in printed}==printed
    return dict(actual_reasons=counts,reason_literals=total,example=examples,outer=outer,
                joint=joint,cost=cost,by_width=per_width)


def main():
    folder=HERE/"results"/sys.argv[1]
    manifest=json.loads((folder/"manifest.json").read_text())
    result={}
    for dest in sorted(folder.glob("*-*-*")):
        if not dest.is_dir():
            continue
        t,_,m=dest.name.split("-")
        path=dest/("solver.log.gz" if manifest["kind"].endswith("trace") else "solver.log")
        result[t+"-"+m]=assess(path,m)
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
