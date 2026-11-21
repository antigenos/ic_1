"""Build into this checkout; an external prepared ABC tree is read-only input."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import build_variant


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, default=ROOT,
                        help="checkout containing the pinned ABC objects and TCJAP core")
    parser.add_argument("--build-frozen",action="store_true",help="also build the unmodified joint executable in this checkout")
    parser.add_argument("--restriction",action="store_true",help="build the separate cofactor-bound experiment executable")
    parser.add_argument("--endpoint",action="store_true",help="build the separate joint-endpoint executable")
    args = parser.parse_args()
    prepared = args.prepared.resolve()
    build_variant.ABC = prepared/".local/abc"
    # The baseline compiler includes the headers in its prepared checkout.
    for name in ("joint_trail.h","histograms.h","trail_clause.h"):
        if (prepared/"tools"/name).read_text() != (ROOT/"tools"/name).read_text():
            raise ValueError("Mismatched frozen include: "+name)
    src = prepared/".local/reference/src"
    dest = ROOT/".local/reference/src"
    if dest != src:
        dest.mkdir(parents=True,exist_ok=True)
        for name in ("joint_relation.c","joint_relation.h"):
            shutil.copyfile(src/name,dest/name)
    name = "endpoint-01a1fb7c" if args.endpoint else ("restriction-01a1fb7c" if args.restriction else "signed-symmetry-confirmed-01a1fb7c")
    out = ROOT/".local/variants"/name
    out.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(HERE/"first_gate.h",out/"first_gate.h")
    shutil.copyfile(HERE/"pair_gate.h",out/"pair_gate.h")
    shutil.copyfile(HERE/"chain_order.h",out/"chain_order.h")
    patches = [ROOT/"variants"/(s+".patch") for s in ("compositions","support","joint-trail")]
    study_patches = [HERE/"first-gate.patch"]
    if args.restriction or args.endpoint:
        shutil.copyfile(HERE/"restriction_filter.h",out/"restriction_filter.h")
        subprocess.run([sys.executable,str(HERE/"restriction.py"),"--header",str(out/"restriction_table.h")],check=True)
        study_patches.append(HERE/"restriction.patch")
    if args.endpoint:
        shutil.copyfile(HERE/"endpoint_filter.h",out/"endpoint_filter.h")
        subprocess.run([sys.executable,str(HERE/"endpoint.py"),"--header",str(out/"endpoint_table.h")],check=True)
        study_patches.append(HERE/"endpoint.patch")
    patchdir = out/"patches"
    patchdir.mkdir(exist_ok=True)
    for patch in [*patches,*study_patches,ROOT/"variants/sat-trail.patch"]:
        (patchdir/patch.name).write_text(patch.read_text(), encoding="utf-8", newline="\n")
    if args.build_frozen:
        build_variant.build("joint",[patchdir/p.name for p in patches],patchdir/"sat-trail.patch")
    build_variant.build(name,[patchdir/p.name for p in [*patches,*study_patches]],
                        patchdir/"sat-trail.patch")
    binary = out/("abc.exe" if sys.platform == "win32" else "abc")
    with binary.open("rb") as stream:
        print("SHA256", hashlib.file_digest(stream,"sha256").hexdigest())


if __name__ == "__main__":
    main()
