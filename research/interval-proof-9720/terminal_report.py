"""Recompute paired bounded-proof results from the public measurements CSV."""
import argparse
import csv
import json
from math import exp, fsum, log
from pathlib import Path

from audit_host import exposure
from family import HERE
from terminal_compare import PLAN, STORAGE_PLAN, holdout_plan


METHOD = {"A": "full_enumeration", "T": "terminal_output_matching", "D": "deduplicated_terminal_matching"}


def host_exposures(raw, sample_file, plan, rows):
    records = [json.loads(line) for line in raw.read_bytes().splitlines()]
    samples = [json.loads(line) for line in sample_file.read_bytes().splitlines()]
    post = sample_file.with_name("post-sample.json")
    if post.is_file():
        samples.append(json.loads(post.read_bytes()))
    epochs = [s["epoch"] for s in samples]
    assert epochs and all(b > a for a, b in zip(epochs, epochs[1:]))
    assert [(r["truth"], r["strict_cap"], r["arm"]) for r in records] == plan
    assert len({tuple(r["child_affinity"]) for r in records}) == 1
    flags = []
    for r, row in zip(records, rows):
        assert float(row["capped_elapsed_s"]) == min(300, r["wall_s"])
        assert (row["outcome"] == "timeout") == (r["status"] == "timeout")
        cpu, = r["child_affinity"]
        flags.append(exposure(dict(r, experiment={"cpu": cpu}), samples, epochs))
    return flags


def summarize(source, panel, raw=None, samples=None):
    bounds = json.loads((HERE / "evidence/constructed-through-432.json").read_bytes())["bounds"]
    if panel == "holdout":
        register = json.loads((HERE / "evidence/terminal-holdout-plan.json").read_bytes())
        assert register == holdout_plan(bounds)
        plan = [(case["truth"], register["strict_cap"], arm) for case in register["cases"] for arm in case["order"]]
    else:
        plan = STORAGE_PLAN if panel == "storage" else PLAN
    baseline = "D" if panel == "storage" else "A"
    with source.open(encoding="utf8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len(plan)
    flags = host_exposures(raw, samples, plan, rows) if raw is not None else None
    pairs = []
    for i in range(0, len(plan), 2):
        truth, cap, _ = plan[i]
        expected = bounds["lower_bounds"][truth]
        goal = "optimum" if expected < cap else "lower_bound"
        measured, times = {}, {}
        for j in (i, i+1):
            t, c, arm = plan[j]
            row = rows[j]
            assert (t, c) == (truth, cap)
            assert (int(row["order"]), row["truth"], int(row["strict_activity_cap"]), row["method"]) == (j+1, t, c, METHOD[arm])
            seconds = float(row["capped_elapsed_s"])
            assert int(row["timeout_s"]) == 300 and 0 < seconds <= 300
            if row["outcome"] == "timeout":
                assert seconds >= 299.95 and not row["optimum"] and not row["gates"]
            elif goal == "optimum":
                assert row["outcome"] == "completed" and int(row["optimum"]) == expected and int(row["gates"]) > 0
            else:
                assert row["outcome"] == "proved_no_solution_below_cap" and not row["optimum"] and not row["gates"]
            measured[arm] = row
            times[arm] = seconds
        both = all(r["outcome"] != "timeout" for r in measured.values())
        pair = dict(truth=truth, order=plan[i][2]+plan[i+1][2], goal=goal, optimum=expected if goal=="optimum" else None,
                    capped_s=times, timed_out=[a for a, r in measured.items() if r["outcome"] == "timeout"],
                    ratio=times[baseline]/times["T"] if both else None)
        if flags is not None:
            pair["host_flags"] = sorted(flags[i] | flags[i+1])
        if panel == "storage" and both:
            d, t = measured["D"], measured["T"]
            assert d["expanded_states"] == t["expanded_states"] and d["terminal_edges"] == t["terminal_edges"]
            checks = {a: int(r["terminal_check_calls"]) for a,r in measured.items()}
            assert 0 < checks["D"] == int(d["retained_terminal_states"]) <= checks["T"]
            assert int(t["retained_terminal_states"]) == 0 and checks["T"] <= int(t["terminal_edges"])
            pair.update(check_calls=checks, stored_keys_D=checks["D"], terminal_edges=int(t["terminal_edges"]))
        if panel == "storage" and all(r.get("peak_working_set_bytes") for r in measured.values()):
            peak = {a: int(r["peak_working_set_bytes"]) for a,r in measured.items()}
            assert all(n > 0 for n in peak.values())
            pair["peak_working_set_MiB"] = {a: n/(1024**2) for a,n in peak.items()}
        pairs.append(pair)
    groups = {}
    for goal in ("optimum", "lower_bound"):
        cohort = [p for p in pairs if p["goal"] == goal]
        ratios = [p["ratio"] for p in cohort if p["ratio"] is not None]
        groups[goal] = dict(pairs=len(cohort), both_finished=len(ratios), faster_T=sum(r>1 for r in ratios),
                            paired_gm=exp(fsum(map(log, ratios))/len(ratios)) if ratios else None,
                            capped_s={a: fsum(p["capped_s"][a] for p in cohort) for a in (baseline,"T")})
    result = dict(panel=panel, baseline=baseline, groups=groups, pairs=pairs)
    if panel == "holdout":
        g = groups["optimum"]
        result["registered_timing_criterion_met"] = g["both_finished"] == 6 and g["faster_T"] >= 4 and g["paired_gm"] > 1
    return result


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("measurements", type=Path)
    cli.add_argument("panel", choices=("pilot", "holdout", "storage"))
    cli.add_argument("--local-host-audit", type=Path, nargs=2, metavar=("TRIALS", "SAMPLES"))
    args = cli.parse_args()
    print(json.dumps(summarize(args.measurements, args.panel, *(args.local_host_audit or ())), indent=2))
