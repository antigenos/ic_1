"""Reconstruct paired results and verify every circuit from the exported family shards."""
import argparse
from collections import Counter
import hashlib
import json
from math import exp, fsum, isclose, log
from pathlib import Path
import re
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
from witness import simulate

METHODS = ["base", "wide-highplain", "wide-hightail"]
COMPLETED = "solver_completed_verified_witness"


def audit(folder, full):
    plan = json.loads((folder/"manifest.json").read_text())
    summary = json.loads((folder/"summary.json").read_text())
    assert plan["modes"] == METHODS and plan["budget"]==480 and plan["proof_work"]==20000000
    assert plan["binary_sha256"][METHODS[1]] == plan["binary_sha256"][METHODS[2]]
    if full:
        with ZipFile(HERE/"reproduction.zip") as archive:
            assert plan["cases"] == json.loads(archive.read("evidence/e14-main/manifest.json"))["cases"]
        assert len(plan["cases"]) == 208 and plan["cap"] == 300
    results, routes = {}, {}
    activities = {}
    for m, mode in enumerate(METHODS):
        rows, paths = [], Counter()
        for shard in sorted(folder.glob(mode+"-*.jsonl")):
            rows.extend(json.loads(line) for line in shard.read_text(encoding="utf-8").splitlines())
        assert len(rows) == len(plan["cases"])
        for i, row in enumerate(rows):
            target = plan["cases"][i]
            cpu = plan["cpus"][i%len(plan["cpus"])]
            assert row["experiment"] == dict(truth=target,mode=mode,order=(m-i)%3,cpu=cpu)
            assert row["child_affinity"]==[cpu] and row["timeout_s"]==plan["cap"]
            assert row["binary_sha256"]==plan["binary_sha256"][mode]
            assert row["command"][1:] == ["-c", f"pexact -I 4 -M 2 {target}"]
            message = row["solver_output"]
            assert hashlib.sha256(message.encode()).hexdigest()==row["solver_log_sha256"]
            assert isclose(row["capped_wall_s"], min(row["wall_s"],plan["cap"]))
            if row["status"] == "timeout":
                assert row["wall_s"]>=plan["cap"] and "witness" not in row
                paths["timed_out"] += 1
                continue
            assert row["status"]==COMPLETED and row["returncode"]==0 and "Total runtime" in message
            witness = simulate(message, 4, int(target,16))
            assert witness == row["witness"]
            assert activities.setdefault(target,witness["activity"])==witness["activity"]
            if mode == "base":
                paths["native_search"] += 1
                continue
            hit = re.search(r"FF_BOUND complete=(\d) found=(\d) paid=(-?\d+) nodes=(\d+) pruned=(\d+)",message)
            assert hit
            finished, found, paid, visited, pruned = map(int, hit.groups())
            assert 0 < visited <= plan["proof_work"] and pruned <= visited
            if "FF_NATIVE" in message:
                assert finished and found and paid==witness["activity"]
                paths["bounded_optimum_confirmed_by_native_cnf"] += 1
            elif finished and not found:
                assert witness["activity"]>plan["budget"]
                paths["native_search_above_proven_budget"] += 1
            elif finished:
                assert found and witness["activity"]==paid
                paths["native_search_from_proven_optimum"] += 1
            else:
                assert visited==plan["proof_work"]
                paths["native_search_after_work_limit"] += 1
        results[mode]=rows
        routes[mode]=dict(paths)
        total=summary["totals"][mode]
        assert total["completed"] == sum(r["status"]==COMPLETED for r in rows)
        assert isclose(total["capped_s"],fsum(r["capped_wall_s"] for r in rows))
    outcomes={}
    for mode in METHODS[:2]:
        ratios, gained, lost = {}, [], []
        for t, left, right in zip(plan["cases"],results[mode],results[METHODS[2]],strict=True):
            if left["status"]==right["status"]==COMPLETED:
                ratios[t]=left["wall_s"]/right["wall_s"]
            elif left["status"]!=right["status"]:
                (gained if right["status"]==COMPLETED else lost).append(t)
        p=summary["comparisons"][mode]
        assert (p["ratios"],p["gained"],p["lost"],p["common"])==(ratios,gained,lost,len(ratios))
        if ratios:
            assert isclose(p["paired_gm"],exp(fsum(map(log,ratios.values()))/len(ratios)))
        else:
            assert p["paired_gm"] is None
        outcomes[mode]=dict(gained=gained,lost=lost,slower_on_jointly_completed={t:v for t,v in ratios.items() if v<1})
    return dict(checked_runs=3*len(plan["cases"]), verified_witnesses=sum(t["completed"] for t in summary["totals"].values()),
                distinct_solved_targets=len(activities),routes=routes,comparisons=outcomes)


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("folder",type=Path)
    p.add_argument("--small", action="store_true", help="Audit an explicitly smaller preflight")
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    result=audit(args.folder, not args.small)
    if args.out:
        args.out.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("comparisons","routes")}))
