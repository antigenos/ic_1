"""Run predeclared paired groups on persistent per-CPU worker processes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys

from repeat_0189 import pin
from run_case import run

ROOT = Path(__file__).resolve().parents[1]
SUFFIX = ".exe" if os.name == "nt" else ""
BINS = {k: ROOT / ".local" / path / ("abc" + SUFFIX) for k, path in
        [("author", "abc"), ("support", "variants/support"), ("joint", "variants/joint")]}
COHORTS = {"main": ["author", "support", "both"],
           "ablation": ["off", "counts", "early", "both", "nobudget"]}
VERIFIED = "solver_completed_verified_witness"


def dump(path, obj):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def worker(dest, cpu):
    plan = load(dest / "manifest.json")
    pin(cpu)
    methods = plan["methods"]
    for idx, truth in enumerate(plan["cases"]):
        if plan["cpus"][idx % len(plan["cpus"])] != cpu:
            continue
        shift = idx % len(methods)
        order = methods[shift:] + methods[:shift]
        for position, method in enumerate(order):
            role = method if method in ("author", "support") else "joint"
            info = dict(truth=truth, method=method, cpu=cpu, order=position, cohort=plan["cohort"])
            case = dest / truth / method
            if (case / "result.json").is_file():
                prior = load(case / "result.json")
                if (prior.get("experiment") != info or
                    prior["binary_sha256"] != plan["binary_sha256"][role] or
                    prior["timeout_s"] != plan["seconds"]):
                    raise RuntimeError(f"Prior run differs: {case}")
                continue
            if case.exists():
                raise RuntimeError(f"Inspect existing run before recovery: {case}")
            env = {k: v for k, v in os.environ.items() if not k.startswith("REPLAY_")}
            if role == "joint":
                env["REPLAY_RULES"] = "both" if method == "nobudget" else method
                env["REPLAY_BUDGET"] = "0" if method == "nobudget" else "1"
            record = run(BINS[role], truth, 4, 2, plan["seconds"], case, env=env, metadata=info)
            if record["binary_sha256"] != plan["binary_sha256"][role]:
                raise RuntimeError("Executable changed during an experiment")
            if record["status"] not in (VERIFIED, "timeout"):
                raise RuntimeError(f"Inspect failed verification: {case}")


def summary(dest, plan):
    results = {m: {} for m in plan["methods"]}
    for truth in plan["cases"]:
        verified = set()
        for m in results:
            item = load(dest / truth / m / "result.json")
            if item["status"] == VERIFIED:
                verified.add(item["witness"]["activity"])
            elif item["status"] != "timeout":
                raise ValueError(f"Invalid run for {truth}/{m}")
            results[m][truth] = item
        if len(verified) > 1:
            raise ValueError(f"Disagreeing activities for {truth}: {verified}")
    totals = {m: dict(completed=sum(v["status"] == VERIFIED for v in group.values()),
                      capped_s=sum(v["capped_wall_s"] for v in group.values()))
              for m, group in results.items()}
    pairs = {}
    for baseline, group in results.items():
        if baseline == "both":
            continue
        ratios = {t: v["wall_s"]/results["both"][t]["wall_s"] for t, v in group.items()
                  if v["status"] == VERIFIED and results["both"][t]["status"] == VERIFIED}
        pairs[baseline] = dict(common=len(ratios), gm=math.exp(sum(map(math.log, ratios.values())) /
                               len(ratios)) if ratios else None, ratios=ratios)
    return dict(totals=totals, baseline_over_both=pairs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dest", type=Path)
    parser.add_argument("--cohort", choices=COHORTS)
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--cpus", nargs="+", type=int, default=[2])
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--worker", type=int)
    args = parser.parse_args()
    dest = args.dest.resolve()
    if args.worker is not None:
        worker(dest, args.worker)
        return
    if not args.cohort or not args.cases or args.seconds <= 0:
        parser.error("Supply cohort, cases and a positive timeout")
    if args.cases == ["essential"]:
        from function_family import family
        cases = family()["essential"]
    else:
        cases = [f"{int(t, 16):04x}" for t in args.cases]
    if len(set(cases)) != len(cases) or len(set(args.cpus)) != len(args.cpus):
        raise ValueError("Repeated case or CPU")
    methods = COHORTS[args.cohort]
    needed = set(BINS) if args.cohort == "main" else {"joint"}
    hashes = {k: hashlib.sha256(BINS[k].read_bytes()).hexdigest() for k in sorted(needed)}
    plan = dict(cohort=args.cohort, cases=cases, methods=methods, seconds=args.seconds,
                cpus=args.cpus, platform=platform.platform(), binary_sha256=hashes)
    if dest.exists():
        if not (dest / "manifest.json").exists() or load(dest / "manifest.json") != plan:
            raise RuntimeError("Existing directory has a different or missing manifest")
    else:
        dest.mkdir(parents=True)
        dump(dest / "manifest.json", plan)
    def launch(cpu):
        subprocess.run([sys.executable, __file__, str(dest), "--worker", str(cpu)], check=True)
    with ThreadPoolExecutor(max_workers=len(args.cpus)) as pool:
        list(pool.map(launch, args.cpus))
    result = summary(dest, plan)
    dump(dest / "summary.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
