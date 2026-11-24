"""Rebuild key proofs and replay all held-out designs from a clean public checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

STUDY=Path("experiments/fixed-fanin-01a1fb7c/support-frontier")


def read(path):
    return json.loads(path.read_text())


def main():
    parser=argparse.ArgumentParser()
    for arg in ("checkout","scratch","inputs","abc","certificate_abc","report"):
        parser.add_argument(arg,type=Path)
    args=parser.parse_args()
    root=args.checkout.resolve()
    work=args.scratch.resolve()
    work.mkdir(parents=True,exist_ok=False)
    if args.report.exists():
        raise FileExistsError(args.report)
    study=root/STUDY
    evidence=study/"evidence"
    def git(*cmd):
        return subprocess.check_output(["git",*cmd],cwd=root,text=True).strip()
    assert not git("status","--porcelain")
    report=dict(commit=git("rev-parse","HEAD"),tree=git("show","-s","--format=%T","HEAD"),steps={})
    def run(label,command):
        start=time.perf_counter()
        result=subprocess.run(list(map(str,command)),cwd=root,capture_output=True)
        if result.returncode:
            raise RuntimeError(f"{label} failed: {result.stderr[-3000:]!r} {result.stdout[-1000:]!r}")
        report["steps"][label]=dict(wall_s=time.perf_counter()-start,
                                   stdout_sha256=hashlib.sha256(result.stdout).hexdigest())
        print(label,round(report["steps"][label]["wall_s"],2),flush=True)
    def py(label,file,*params):
        run(label,[sys.executable,study/file,*params])
    py("archive_audit","summarize.py")
    binaries={}
    for name in ("frontier","postfix"):
        binary=work/(name+(".exe" if sys.platform=="win32" else ""))
        run("rebuild_"+name,["g++","-O3","-std=c++17",STUDY/(name+".cpp"),
                             "-o",os.path.relpath(binary,root)])
        binaries[name]=binary
    frontier=work/"six.json"
    py("fresh_six_forward","run.py",binaries["frontier"],6,3664,2,frontier)
    assert read(frontier)["witnesses"]==read(evidence/"held-6-3664-2.json")["witnesses"]
    postfix=work/"six-postfix.json"
    py("fresh_six_postfix","crosscheck.py",binaries["postfix"],frontier,postfix)
    old=read(evidence/"postfix-held-6-3664-2.json")
    for field in ("visits","live_expressions","represented_labeled_outputs","classes","stdout_sha256"):
        assert read(postfix)[field]==old[field]
    py("tree_and_native","verify_pareto.py",work/"trees.json","--abc",args.certificate_abc.resolve())
    for field in ("all_four_tables","recognized_four","splits","heldout_labels"):
        assert read(work/"trees.json")[field]==read(evidence/"pareto-audit.json")[field]
    py("fresh_joint_dp","verify_correlated.py",work/"small-dp.json")
    assert read(work/"small-dp.json")==read(evidence/"correlated-small.json")
    out=work/"transfer"
    py("all_twenty_heldout","workload.py",args.inputs.resolve(),args.abc.resolve(),work/"aigs",evidence/"epfl",out)
    assert len(list(out.glob("*.json")))==20
    targets={}
    for file in sorted(out.glob("*.json")):
        a,b=read(file),read(evidence/"transfer"/file.name)
        for field in ("panels","training_counts","training_savings","source_sha256","cut_sha256",
                      "areas","depths","size_changes","sharing_changes"):
            assert a[field]==b[field],(file.name,field)
        for x,y in zip(a["equivalence"],b["equivalence"],strict=True):
            assert x.get("sha256")==y.get("sha256")
            if x.get("identity"):
                assert x==y
            else:
                assert "Networks are equivalent" in x["output"]
        targets[file.stem]=[sum(col) for col in zip(*a["panels"])]
    assert not git("status","--porcelain")
    report.update(clean=True,six_classes=old["classes"],empirical_deadline_checks=394,
                  designs=len(targets),heldout_transitions=list(map(sum,zip(*targets.values()))),
                  matched_all_panels_topologies_depths=True,
                  reused_inputs="Pinned EPFL AIGs by blob hash and previously built pinned ABC validators")
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    print("Clean checkout accepted:",report["commit"],report["heldout_transitions"])


if __name__=="__main__":
    main()
