"""Decode same-call original/candidate clauses and identify later watched conflicts."""
from collections import Counter, defaultdict
import sys,gzip,json
from pathlib import Path
D=Path(__file__).resolve().parent
sys.path.insert(0,str(D.parent/"tools"))
from audit_trail import audit

def check(log,role):
    stats=defaultdict(Counter)
    lengths=defaultdict(Counter)
    expected=Counter()
    work=[]
    handles={}
    binaries={}
    original=None
    handle=None
    first={}
    query=0
    with gzip.open(log,"rt",errors="strict") as f:
        for line in f:
            fields=line.split()
            if not fields: continue
            tag=fields[0]
            if tag=="QUERY":
                handles.clear(); binaries.clear(); query+=1
            elif tag=="HANDLE":
                assert handle is None
                handle=int(fields[1])
            elif tag=="ORIGINAL":
                assert original is None
                original=tuple(map(int,fields[1:]))
            elif tag=="REASON":
                kind=audit(line)
                new=tuple(map(int,fields[8:]))
                raw=original if role=="online" else new
                assert raw and handle is not None and raw[0]==new[0] and set(new)<=set(raw)
                assert len(set(raw))==len(raw)
                if role=="online":
                    assert audit(" ".join(fields[:8]+list(map(str,raw))))==kind
                record=(kind,tuple(sorted(new)),len(raw),len(new))
                handles[handle]=record
                if len(new)==2: binaries[record[1]]=record
                stats[kind]["propagated"]+=1
                stats[kind]["shortened"]+=len(new)<len(raw)
                lengths[kind+"/original"][len(raw)]+=1
                lengths[kind+"/emitted"][len(new)]+=1
                original=handle=None
            elif tag=="GC":
                moved={}
            elif tag=="MOVE":
                a,b=map(int,fields[1:])
                if a in handles: moved[b]=handles[a]
            elif tag=="ENDGC": handles=moved
            elif tag=="CLASH":
                h=int(fields[1]); lits=tuple(sorted(map(int,fields[2:])))
                record=binaries.get(lits) if h==-1 else handles.get(h)
                stats["all"]["active_query_conflicts"]+=1
                if record:
                    kind, actual, before, after=record
                    assert actual==lits
                    key="binary_content_match" if h==-1 else "identified_conflict"
                    stats[kind][key]+=1
                    stats[kind][key+"_shortened"]+=after<before
                    lengths[kind+"/"+key+"_before"][before]+=1
                    lengths[kind+"/"+key+"_after"][after]+=1
                    first.setdefault(kind+"/"+key,dict(query=query,handle=h,clause=lits,original_length=before))
            elif tag=="JOINT":
                data=dict(x.split("=") for x in fields[1:])
                expected.update(count=int(data["counts"]),sel=int(data["edges"]))
            elif tag=="WORK": work.append(list(map(int,fields[1:])))
    assert original is None and handle is None and query==len(work)>0
    for kind in ("count","sel"): assert expected[kind]==stats[kind]["propagated"]
    return dict(queries=query,events=stats,length_histograms=lengths,examples=first,work=work)
