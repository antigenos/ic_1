"""Replay exported solver outputs and independently recompute paired and capped outcomes."""
import argparse
import hashlib
import json
from math import exp, fsum, isclose, log
from pathlib import Path

from witness import simulate


def audit(dest):
    plan = json.loads((dest / "manifest.json").read_text())
    published = json.loads((dest / "summary.json").read_text())
    methods, cases = plan["methods"], plan["cases"]
    reduced = {}
    activities = {t: set() for t in cases}
    completed = "solver_completed_verified_witness"
    for method in methods:
        group = {}
        role = method if method in ("author", "support") else "joint"
        for entry in (dest / (method + ".jsonl")).read_text().splitlines():
            row = json.loads(entry)
            info = row["experiment"]
            t = info["truth"]
            i = len(group)
            assert t == cases[i] and t not in group
            assert info["method"] == method and info["cohort"] == plan["cohort"]
            assert info["cpu"] == plan["cpus"][i % len(plan["cpus"])]
            assert info["order"] == (methods.index(method) - i) % len(methods)
            if "child_affinity" in row:
                assert row["child_affinity"] == [info["cpu"]] and row["pid"] > 0
            assert row["command"][1:] == ["-c", f"pexact -I 4 -M 2 {t}"]
            assert row["timeout_s"] == plan["seconds"]
            assert row["binary_sha256"] == plan["binary_sha256"][role]
            text = row["solver_output"]
            assert hashlib.sha256(text.encode()).hexdigest() == row["solver_log_sha256"]
            assert row["wall_s"] >= 0 and isclose(row["capped_wall_s"], min(row["wall_s"], plan["seconds"]))
            if row["status"] == completed:
                assert row["returncode"] == 0 and "Total runtime" in text
                check = simulate(text, 4, int(t, 16))
                assert check == row["witness"]
                activities[t].add(check["activity"])
            else:
                assert row["status"] == "timeout" and "witness" not in row
                assert isclose(row["capped_wall_s"], plan["seconds"], abs_tol=0.01)
            group[t] = row
        assert list(group) == cases
        observation = published["totals"][method]
        assert observation["completed"] == sum(row["status"] == completed for row in group.values())
        assert isclose(observation["capped_s"], fsum(row["capped_wall_s"] for row in group.values()))
        reduced[method] = group
    assert all(len(a) <= 1 for a in activities.values())
    comparisons = {}
    for method in methods:
        if method == "both":
            continue
        left, right = reduced[method], reduced["both"]
        paired = {t: left[t]["wall_s"] / right[t]["wall_s"] for t in cases
                  if left[t]["status"] == right[t]["status"] == completed}
        p = published["baseline_over_both"][method]
        assert p["common"] == len(paired) and p["ratios"] == paired
        if paired:
            assert isclose(p["gm"], exp(fsum(log(v) for v in paired.values()) / len(paired)))
        else:
            assert p["gm"] is None
        comparisons[method] = dict(
            completed_only_by_reconstruction=[t for t in cases if left[t]["status"] != completed and right[t]["status"] == completed],
            completed_only_by_control=[t for t in cases if left[t]["status"] == completed and right[t]["status"] != completed],
            slower_on_jointly_finished={t: v for t, v in sorted(paired.items(), key=lambda pair: pair[1]) if v < 1})
    return dict(checked_runs=len(cases)*len(methods), verified_witnesses=sum(
        s["completed"] for s in published["totals"].values()), functions=len(cases),
        distinct_values_agree=True, comparisons=comparisons)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("export", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.export)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "comparisons"}))
