"""Run or export the preregistered three-arm, cold-process, four-input family comparison."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from math import exp, log
import os
from pathlib import Path
import platform
import subprocess
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/"tools"))
from repeat_0189 import pin
from run_case import run
from witness import simulate

MODES = ("base", "wide-highplain", "wide-hightail")
DONE = "solver_completed_verified_witness"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def binary(mode):
    name = "base" if mode == "base" else "tail"
    return ROOT/".local/variants"/("fixed-fanin-"+name)/("abc.exe" if os.name == "nt" else "abc")


def order(index):
    offset = index % len(MODES)
    return MODES[offset:] + MODES[:offset]


def worker(folder, index):
    plan = read(folder/"manifest.json")
    cpu = plan["cpus"][index]
    pin(cpu)
    for i in range(index, len(plan["cases"]), len(plan["cpus"])):
        truth = plan["cases"][i]
        for k, mode in enumerate(order(i)):
            path = folder/truth/mode
            info = dict(truth=truth, cpu=cpu, mode=mode, order=k)
            if (path/"result.json").exists():
                result = read(path/"result.json")
            elif path.exists():
                raise RuntimeError(f"Run already exists without its final record: {path}")
            else:
                env = {a:b for a,b in os.environ.items() if not a.startswith(("FF_", "REPLAY_"))}
                env.update(FF_MODE=mode, FF_BOUNDED_STATS="1")
                result = run(binary(mode), truth, 4, 2, plan["cap"], path, env=env, metadata=info)
            if (result["experiment"] != info or result["binary_sha256"] != plan["binary_sha256"][mode]
                    or result["child_affinity"] != [cpu] or result["timeout_s"] != plan["cap"]
                    or result["status"] not in (DONE, "timeout")):
                raise RuntimeError(f"Invalid outcome: {path}")
        write(folder/f"cpu-{cpu}.json", dict(last_completed=truth, completed=1+(i-index)//len(plan["cpus"])))


def export(folder, dest):
    plan = read(folder/"manifest.json")
    entries = {mode:[] for mode in MODES}
    for i, truth in enumerate(plan["cases"]):
        activities = set()
        for k, mode in enumerate(order(i)):
            path = folder/truth/mode
            r = read(path/"result.json")
            req = read(path/"request.json")
            launch = read(path/"launch.json")
            cpu = plan["cpus"][i % len(plan["cpus"])]
            assert all(r[key] == v for key,v in {**req, **launch}.items())
            assert r["child_affinity"] == [cpu]
            assert r["experiment"] == dict(truth=truth, cpu=cpu, mode=mode, order=k)
            assert r["binary_sha256"] == plan["binary_sha256"][mode] and r["timeout_s"] == plan["cap"]
            assert r["command"][1:] == ["-c", f"pexact -I 4 -M 2 {truth}"]
            raw = (path/"solver.log").read_bytes()
            r["solver_output"] = raw.decode()
            r["solver_log_sha256"] = hashlib.sha256(raw).hexdigest()
            assert r["capped_wall_s"] == min(r["wall_s"], plan["cap"])
            if r["status"] == DONE:
                assert r["returncode"] == 0 and "Total runtime" in r["solver_output"]
                assert simulate(r["solver_output"], 4, int(truth,16)) == r["witness"]
                activities.add(r["witness"]["activity"])
            else:
                assert r["status"] == "timeout" and r["wall_s"] >= plan["cap"]
            entries[mode].append(r)
        assert len(activities) <= 1
    dest.mkdir(parents=True, exist_ok=True)
    write(dest/"manifest.json", plan)
    totals = {}
    for mode, rows in entries.items():
        totals[mode] = dict(completed=sum(r["status"]==DONE for r in rows),
                            capped_s=sum(r["capped_wall_s"] for r in rows))
        for start in range(0, len(rows), 26):
            block = rows[start:start+26]
            (dest/f"{mode}-{start//26+1:02}.jsonl").write_text("".join(
                json.dumps(r, ensure_ascii=True, separators=(",", ":"))+"\n" for r in block), encoding="utf-8")
    comparisons = {}
    for mode in MODES[:-1]:
        ratios, gained, lost = {}, [], []
        for a, b in zip(entries[mode], entries[MODES[-1]], strict=True):
            truth = a["experiment"]["truth"]
            if a["status"] == b["status"] == DONE:
                ratios[truth] = a["wall_s"]/b["wall_s"]
            elif a["status"] != b["status"]:
                (gained if b["status"] == DONE else lost).append(truth)
        comparisons[mode] = dict(common=len(ratios), paired_gm=exp(sum(map(log,ratios.values()))/len(ratios))
                                 if ratios else None, gained=gained, lost=lost, ratios=ratios)
    ans = dict(totals=totals, comparisons=comparisons)
    write(dest/"summary.json", ans)
    print(json.dumps(totals))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--cpus", nargs="+", type=int)
    parser.add_argument("--cases", nargs="+", default=["essential"])
    parser.add_argument("--cap", type=int, default=300)
    parser.add_argument("--worker", type=int)
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    folder = args.directory.resolve()
    if args.worker is not None:
        worker(folder, args.worker)
    elif args.export:
        export(folder, args.export)
    else:
        if not args.cpus or len(set(args.cpus))!=len(args.cpus) or args.cap<=0:
            parser.error("Choose distinct logical CPUs and a positive cap")
        with ZipFile(HERE/"reproduction.zip") as archive:
            family = json.loads(archive.read("evidence/e14-main/manifest.json"))["cases"]
        cases = family if args.cases==["essential"] else [f"{int(t,16):04x}" for t in args.cases]
        if not set(cases)<=set(family) or len(set(cases))!=len(cases):
            parser.error("Choose distinct functions in the original essential family")
        plan = dict(cases=cases, cpus=args.cpus, cap=args.cap, modes=MODES, platform=platform.platform(),
                    budget=480, proof_work=20000000,
                    binary_sha256={m:hashlib.sha256(binary(m).read_bytes()).hexdigest() for m in MODES})
        plan["modes"] = list(MODES)
        if folder.exists():
            if read(folder/"manifest.json") != plan:
                raise RuntimeError("A different batch uses this destination")
        else:
            folder.mkdir(parents=True)
            write(folder/"manifest.json", plan)
        def launch(i):
            subprocess.run([sys.executable, __file__, str(folder), "--worker", str(i)], check=True)
        with ThreadPoolExecutor(max_workers=len(args.cpus)) as pool:
            list(pool.map(launch, range(len(args.cpus))))
        print("Completed", len(cases)*len(MODES), "runs.", flush=True)
