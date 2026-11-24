"""Summarize timed pairs, instrumented work and reason audits without imputing optima."""
import argparse, gzip, json, math, statistics
from pathlib import Path
from collections import Counter
D=Path(__file__).resolve().parent
ROLES=("joint","short","online")
def read(p): return json.loads(p.read_bytes())
def good(r): return r["status"]=="solver_completed_verified_witness"

def summarize(timed,trace,profile):
    for folder in (timed,trace,profile):
        assert read(folder/"complete.json")["observed_overlap"]==0
    cases=read(timed/"manifest.json")["cases"]
    data={}
    diagnostics={}
    for t in cases:
        data[t]={}
        diagnostics[t]={}
        for role in ROLES:
            files=sorted(timed.glob(t+"-*-"+role+"/result.json"))
            rows=[read(p) for p in files]
            assert len(rows)==2
            assert all(r["status"] in ("timeout","solver_completed_verified_witness") for r in rows)
            data[t][role]=[dict(completed=good(r),seconds=r["capped_wall_s"]) for r in rows]
            (tr,)=trace.glob(t+"-*-"+role+"/audit.json")
            (pr,)=profile.glob(t+"-*-"+role+"/profile.json")
            a=read(tr); w=read(pr)
            # Trace changes only the instrumentation cost. Check equal deterministic work.
            assert [x[:5]+x[8:] for x in a["work"]]==[x[:5]+x[8:] for x in w],(t,role)
            tot=[sum(x[i] for x in w) for i in range(10)]
            assert len({x[7] for x in w})==1
            diagnostics[t][role]=dict(queries=len(w),conflicts=tot[0],decisions=tot[1],
                bcp_propagations=tot[2],count_attempts=tot[3],edge_attempts=tot[4],
                explanation_ms=[1000*tot[i]/w[0][7] for i in (5,6)],
                fallback=tot[8:10],events=a["events"],lengths=a["length_histograms"],
                prefix=(pr.parent/"prefix.json").exists())
    out={}
    for split,subset in [("development",cases[:2]),("confirmation",cases[2:]),("all",cases)]:
        group={}
        for role in ROLES:
            rows=[r for t in subset for r in data[t][role]]
            group[role]=dict(completed_runs=sum(r["completed"] for r in rows),runs=len(rows),
                completed_functions=sum(all(r["completed"] for r in data[t][role]) for t in subset),
                functions=len(subset),capped_seconds=sum(r["seconds"] for r in rows))
        for control in ROLES[:2]:
            pairs=[(data[t][control][i]["seconds"],data[t]["online"][i]["seconds"]) for t in subset
                   for i in range(2) if data[t][control][i]["completed"] and data[t]["online"][i]["completed"]]
            group[control+"_vs_online"]=dict(common_runs=len(pairs),
                control_seconds=sum(x for x,y in pairs),online_seconds=sum(y for x,y in pairs),
                geometric_speedup=statistics.geometric_mean(x/y for x,y in pairs) if pairs else None)
        out[split]=group
    return dict(summary=out,times=data,diagnostics=diagnostics)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for n in ("timed","trace","profile"): p.add_argument(n,type=Path)
    a=p.parse_args()
    print(json.dumps(summarize(a.timed,a.trace,a.profile),indent=2))
