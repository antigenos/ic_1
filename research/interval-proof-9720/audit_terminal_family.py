"""Audit cold per-target bounded proofs and compare exact coverage to the frozen cohorts."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from math import fsum
from pathlib import Path
from statistics import median
import subprocess
from zipfile import ZipFile

from terminal_compare import HERE, MODULES, PLAN, TERMINAL_REVISION, checked_answer, holdout_plan, terminal_family_plan

FIELDS = ("truth", "origin", "outcome", "capped_elapsed_s", "budget_cost_s", "optimum", "gates")


def read_panel(path, plan):
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    assert [(r["truth"],r["strict_cap"],r["arm"]) for r in rows] == plan
    assert [r["order"] for r in rows] == list(range(1,len(rows)+1))
    return rows


def audit(pilot=None, holdout=None, remaining=None, *, full=None):
    bounds = json.loads((HERE/"evidence/constructed-through-432.json").read_bytes())["bounds"]
    hashes = {}
    for name in MODULES:
        path = (HERE/name).relative_to(HERE.parents[1]).as_posix()
        blob = subprocess.check_output(["git","cat-file","blob",TERMINAL_REVISION+":"+path],cwd=HERE)
        hashes[name] = sha256(blob).hexdigest()
    if full is not None:
        inputs = [(row, "fresh") for row in read_panel(full, terminal_family_plan(bounds))]
    else:
        hp = [(c["truth"],433,a) for c in holdout_plan(bounds)["cases"] for a in c["order"]]
        inputs = [(r,"pilot") for r in read_panel(pilot,PLAN) if r["strict_cap"]==433 and r["arm"]=="T"]
        inputs.extend((r,"holdout") for r in read_panel(holdout,hp) if r["arm"]=="T")
        if remaining is not None:
            inputs.extend((r,"new") for r in read_panel(remaining,terminal_family_plan(bounds,remaining=True)))
    complete = full is not None or remaining is not None
    assert len({r["truth"] for r,_ in inputs}) == len(inputs) == (208 if complete else 9)
    assert len({tuple(r["child_affinity"]) for r,_ in inputs}) == 1 and len(inputs[0][0]["child_affinity"])==1
    with (HERE/"evidence/terminal-holdout-measurements.csv").open(encoding="utf8", newline="") as stream:
        workloads = {(int(row["expanded_states"]), int(row["terminal_edges"])) for row in csv.DictReader(stream)
                     if row["method"] == "terminal_output_matching"}
    if len(workloads) != 1:
        raise ValueError("The frozen confirmation panel does not identify a single traversal workload")
    results = []
    for r,origin in sorted(inputs,key=lambda pair:pair[0]["truth"]):
        assert r["source_sha256"]==hashes and r["timeout_s"]==300 and r["arm"]=="T" and r["strict_cap"]==433
        seconds = min(r["wall_s"],300.)
        assert seconds>0
        witness = {}
        if r["status"]=="completed":
            proof=checked_answer(r,bounds)
            if (proof["states"], proof["terminal_edges"]) not in workloads:
                raise ValueError(f"Traversal counters differ from the frozen panel for {r['truth']}")
            outcome=proof["status"]
            witness=proof.get("witness",{})
        else:
            assert r["status"]=="timeout" and r["wall_s"]>=299.95
            outcome="timeout"
        results.append(dict(truth=r["truth"],origin=origin,outcome=outcome,capped_elapsed_s=seconds,
                            budget_cost_s=seconds if witness else 300.,optimum=witness.get("activity",""),
                            gates=witness.get("gates","")))
    return results, summarize_results(results, complete)


def summarize_results(results, complete):
    exact={r["truth"]:r["optimum"] for r in results if r["outcome"]=="independently_optimal"}
    summary=dict(trials=len(results),exact=len(exact),outcomes=Counter(r["outcome"] for r in results),
                 origins=Counter(r["origin"] for r in results),actual_capped_s=fsum(r["capped_elapsed_s"] for r in results),
                 charging_unresolved_300_s=fsum(r["budget_cost_s"] for r in results))
    if complete:
        summary["frozen_comparisons"]={}
        with ZipFile(HERE/"final-reproduction.zip") as z:
            for arm in ("author","support","both"):
                old=[json.loads(line) for line in z.read("evidence/e14-main/"+arm+".jsonl").splitlines()]
                assert {r["experiment"]["truth"] for r in old}=={r["truth"] for r in results}
                previously={r["experiment"]["truth"]:r["witness"]["activity"] for r in old if "witness" in r}
                common=exact.keys() & previously.keys()
                assert all(exact[t]==previously[t] for t in common)
                summary["frozen_comparisons"][arm]=dict(completed=len(previously),common=len(common),
                    gained=sorted(exact.keys()-previously.keys()),lost=sorted(previously.keys()-exact.keys()))
        times = sorted(r["capped_elapsed_s"] for r in results if r["truth"] in exact)
        threshold = summary["frozen_comparisons"]["both"]["completed"] + 1
        summary["uniform_time_stretch"] = dict(
            preserve_all_exact=300 / times[-1] if times else None,
            exact_needed_to_exceed_frozen=threshold,
            still_exceed_frozen=300 / times[threshold-1] if len(times) >= threshold else None)
    return summary


def summarize_csv(path, session_starts=None):
    bounds = json.loads((HERE / "evidence/constructed-through-432.json").read_bytes())["bounds"]
    expected = bounds["lower_bounds"]
    origins = {truth: "new" for truth in expected}
    origins.update({c["truth"]: "holdout" for c in holdout_plan(bounds)["cases"]})
    origins.update({t: "pilot" for t, cap, arm in PLAN if cap == 433 and arm == "T"})
    with path.open(encoding="utf8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("Unexpected public measurement columns")
        rows = list(reader)
    if len(rows) != 208 or {r["truth"] for r in rows} != set(expected):
        raise ValueError("Each registered function must appear exactly once")
    fresh = all(row["origin"] == "fresh" for row in rows)
    for row in rows:
        truth = row["truth"]
        origin = "fresh" if fresh else origins[truth]
        elapsed = float(row["capped_elapsed_s"])
        cost = float(row["budget_cost_s"])
        if row["origin"] != origin or not 0 < elapsed <= 300:
            raise ValueError(f"Invalid origin or wall time for {truth}")
        if row["outcome"] == "independently_optimal":
            optimum = int(row["optimum"])
            if cost != elapsed or optimum != expected[truth] or optimum >= 433 or int(row["gates"]) <= 0:
                raise ValueError(f"Invalid optimum or budget cost for {truth}")
            row["optimum"] = optimum
        else:
            if row["optimum"] or row["gates"] or cost != 300:
                raise ValueError(f"Unexpected circuit or cost for unresolved target {truth}")
            valid_lower = row["outcome"] == "no_solution_below_cap" and expected[truth] >= 433
            valid_timeout = row["outcome"] == "timeout" and elapsed >= 299.95
            if not (valid_lower or valid_timeout):
                raise ValueError(f"Invalid unresolved outcome for {truth}")
        row.update(capped_elapsed_s=elapsed, budget_cost_s=cost)
    summary = summarize_results(rows, complete=True)
    if session_starts is not None:
        plan = terminal_family_plan(bounds, remaining=not fresh)
        if sorted(set(session_starts)) != session_starts or any(i < 2 or i > len(plan) for i in session_starts):
            raise ValueError("Session starts must be increasing one-based positions after the first trial")
        indexed = {row["truth"]: row for row in rows}
        starts = [1, *session_starts, len(plan)+1]
        sessions = []
        for start, stop in zip(starts, starts[1:]):
            group = [indexed[t] for t, _, _ in plan[start-1:stop-1]]
            bound_only = [r["capped_elapsed_s"] for r in group if r["outcome"] == "no_solution_below_cap"]
            sessions.append(dict(first=start, last=stop-1, outcomes=Counter(r["outcome"] for r in group),
                                 bound_only_median_s=median(bound_only) if bound_only else None))
        summary["timed_sessions"] = sessions
    return summary


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("pilot",type=Path,nargs="?")
    cli.add_argument("holdout",type=Path,nargs="?")
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument("--full",type=Path,help="Audit one fresh 208-function raw run")
    mode.add_argument("--summary-csv",type=Path,help="Recompute statistics from a complete public CSV")
    cli.add_argument("--remaining",type=Path)
    cli.add_argument("--session-starts", type=int, nargs="+",
                     help="With --summary-csv, give the first trial number after each restart in the new-run sequence")
    cli.add_argument("--output",type=Path)
    args=cli.parse_args()
    if args.session_starts and not args.summary_csv:
        cli.error("--session-starts requires --summary-csv")
    if (args.full or args.summary_csv) and (args.pilot or args.holdout or args.remaining):
        cli.error("Choose a fresh run, a public CSV, or the original paired panels")
    if args.summary_csv:
        if args.output:
            cli.error("--summary-csv prints the statistics and takes no output CSV")
        print(json.dumps(summarize_csv(args.summary_csv, args.session_starts),indent=2))
        raise SystemExit(0)
    if not args.full and (not args.pilot or not args.holdout):
        cli.error("The combined audit requires both prior panel files")
    if args.output and not (args.remaining or args.full):
        cli.error("A final export requires all 208 trials")
    results,summary=audit(args.pilot,args.holdout,args.remaining,full=args.full)
    if args.output:
        with args.output.open("x",encoding="utf8",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=FIELDS,lineterminator="\n")
            writer.writeheader()
            writer.writerows(results)
        if summarize_csv(args.output) != summary:
            raise ValueError("Exported measurements disagree with the raw-record audit")
    print(json.dumps(summary,indent=2))
