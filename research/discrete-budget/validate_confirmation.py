"""Check native confirmation clauses, H/T trail identity, binary fingerprints, and the expansion gate."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from build import HERE
from panel import V,FOUR
from summary import summarize,diagnostic,read_querylog


def same_trail(prefix,t):
    folder,=[p.parent for p in (HERE/"results").glob(prefix+"-"+t+"-a*/complete.json")]
    def semantic(m):
        path,=folder.glob(t+"-*-"+m+"/solver.log.gz")
        return [s.strip().split(" seconds=")[0] for s in read_querylog(path)
                if s.startswith(("REASON ","WINDOW_BOUND ","JOINT ","WINDOW "))]
    h,tg=semantic("holes"),semantic("trigger")
    assert h==tg
    return dict(records=len(h),sha256=hashlib.sha256("\n".join(h).encode()).hexdigest())


def main():
    p=argparse.ArgumentParser()
    p.add_argument("timing",nargs="?",default="confirm4")
    p.add_argument("traces",nargs="?",default="post4")
    p.add_argument("--dest",type=Path)
    p.add_argument("--build-manifest",type=Path,default=HERE/"all-builds.json")
    args=p.parse_args()
    timing=summarize(args.timing)
    traces=diagnostic(args.traces)
    assert set(timing["blocks"])==set(V)
    assert set(traces)=={t+"-"+m for t in V for m in FOUR}
    builds=json.loads(args.build_manifest.read_text(encoding="utf-8-sig"))["builds"]
    holdout_proofs={}
    table=[]
    for t in V:
        holdout_proofs[t]=same_trail(args.traces,t)
        for prefix,suffix in ((args.timing,""),(args.traces,"-profile")):
            folder,=[p.parent for p in (HERE/"results").glob(prefix+"-"+t+"-a*/complete.json")]
            plan=json.loads((folder/"manifest.json").read_text())
            assert all(plan["binaries"][m]==builds[m+suffix]["abc.exe"] for m in FOUR)
        for m in FOUR:
            rec=traces[t+"-"+m]
            q,c=rec["joint"],rec["cost"]
            r=rec["actual_reasons"]
            assert sum(r.values())==q["counts"]+q["edges"] and c["frequency"]>0
            table.append(dict(truth=t,method=m,outer_skipped=rec["outer"].get("skip",0),
                sat_queries=sum(rec["outer"].get(k,0) for k in ("1","-1")),
                joint_checks=q["checks"],set_builds=c["builds"],fixed_kernel_calls=c["fixed"],
                member_checks=c["membership"],guard_tests=c.get("trigger_considered",0),
                conflicts=q["conflicts"],decisions=c["decisions"],propagations=c["propagations"],
                reason_attempts=c["reason_attempts"],reason_literals=rec["reason_literals"],
                **{k:r.get(k,0) for k in ("joint_sel","joint_count","interval_sel","interval_count","holes_sel","holes_count")},
                **{k+"_ms":1000*c.get(k+"_ticks",0)/c["frequency"] for k in ("trigger","domain","kernel","reason")}))
        h,tg=traces[t+"-holes"],traces[t+"-trigger"]
        assert h["actual_reasons"]==tg["actual_reasons"] and h["joint"]==tg["joint"]
        assert all(h["cost"][k]==tg["cost"][k] for k in ("decisions","propagations","reason_attempts"))
        assert h["cost"]["calls"]==tg["cost"]["trigger_considered"]
        # A difference in actual outer sequences is reported, never assumed away.
        seq=[traces[t+"-"+m]["outer_sequence"] for m in FOUR]
        holdout_proofs[t]["all_four_outer_sequences_identical"]=all(s==seq[0] for s in seq)
    gates={}
    for mode in ("holes","trigger"):
        wins={m:timing["pairs"][m+"/"+mode]["both_orders_faster"] for m in ("joint","interval")}
        consistent=sorted(set(wins["joint"])&set(wins["interval"]))
        costs=timing["methods"]
        lower_cost=all(costs[mode]["capped_s"]<costs[m]["capped_s"] for m in wins)
        cover=all(costs[mode]["functions_both_orders"]>=costs[m]["functions_both_orders"] for m in wins)
        extra=sum(r["holes_sel"]+r["holes_count"] for r in table if r["method"]==mode)
        gates[mode]=dict(both_orders_faster=wins,same_functions=consistent,lower_capped_total=lower_cost,
                         coverage_preserved=cover,hole_only_reasons=extra,
                         admit_208=(len(consistent)>=3 and lower_cost and cover and extra>0))
    payload=dict(timing=timing,semantic_replay=holdout_proofs,gate=gates)
    if args.dest:
        args.dest.mkdir(parents=True,exist_ok=True)
        (args.dest/"holdout.json").write_text(json.dumps(payload,indent=2)+"\n")
        (args.dest/"holdout-query-audit.json").write_text(json.dumps(traces,indent=2)+"\n")
        with (args.dest/"holdout-overhead.csv").open("w",newline="",encoding="utf8") as stream:
            w=csv.DictWriter(stream,fieldnames=list(table[0]))
            w.writeheader()
            w.writerows(table)
    print(json.dumps(gates,indent=2))


if __name__=="__main__":
    main()
