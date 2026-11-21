"""Build into this checkout; an external prepared ABC tree is read-only input."""
import argparse
import hashlib
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import build_variant


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, default=ROOT,
                        help="checkout containing the pinned ABC objects and TCJAP core")
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
    name = "signed-symmetry-01a1fb7c"
    out = ROOT/".local/variants"/name
    out.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(HERE/"first_gate.h",out/"first_gate.h")
    patches = [ROOT/"variants"/(s+".patch") for s in ("compositions","support","joint-trail")]
    patchdir = out/"patches"
    patchdir.mkdir(exist_ok=True)
    for patch in [*patches,HERE/"first-gate.patch",ROOT/"variants/sat-trail.patch"]:
        (patchdir/patch.name).write_text(patch.read_text(), encoding="utf-8", newline="\n")
    build_variant.build(name,[patchdir/p.name for p in [*patches,HERE/"first-gate.patch"]],
                        patchdir/"sat-trail.patch")
    binary = out/("abc.exe" if sys.platform == "win32" else "abc")
    with binary.open("rb") as stream:
        print("SHA256", hashlib.file_digest(stream,"sha256").hexdigest())


if __name__ == "__main__":
    main()
