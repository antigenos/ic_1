"""Relink only the frozen pexact unit and the new C++ bound into a separate executable."""
import argparse
from hashlib import sha256
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prepared",type=Path,default=ROOT)
    args=p.parse_args()
    abc=args.prepared.resolve()/".local/abc"
    old=ROOT/".local/variants/signed-symmetry-confirmed-01a1fb7c"
    if not (old/"objects.rsp").exists():
        subprocess.run([sys.executable,str(HERE/"build.py"),"--prepared",str(args.prepared)],check=True)
    out=ROOT/".local/variants/closure-01a1fb7c"
    out.mkdir(exist_ok=True)
    for file in ("pexact.c","first_gate.h","pair_gate.h","chain_order.h"):
        shutil.copyfile(old/file,out/file)
    shutil.copyfile(HERE/"closure_author.h",out/"closure_author.h")
    patch=out/"closure.patch"
    patch.write_text((HERE/"closure.patch").read_text(),encoding="utf-8",newline="\n")
    subprocess.run(["git","apply","--directory="+out.relative_to(ROOT).as_posix(),str(patch)],cwd=ROOT,check=True)
    if os.name=="nt":
        flags=["-DWIN32_NO_DLL","-DSIZEOF_VOID_P=8","-DSIZEOF_LONG=4","-DSIZEOF_INT=4"]
        libs=["-lm","-lws2_32","-lpsapi","-lshlwapi"]
    else:
        info=subprocess.check_output(["make","-s","cmake_info","ABC_MAKE_NO_DEPS=1"],cwd=abc,text=True)
        flags=info.split("SEPARATOR_CFLAGS")[1].strip().split()
        libs=info.split("SEPARATOR_LIBS")[1].strip().split()
    for name in ("joint_trail.h","trail_clause.h","histograms.h"):
        if (ROOT/"tools"/name).read_text()!=(args.prepared.resolve()/"tools"/name).read_text():
            raise ValueError(f"Frozen headers differ: {name}")
    subprocess.run(["gcc","-std=gnu11","-O2","-DABC_USE_STDINT_H=1","-DABC_USE_CUDD=1",*flags,
        "-Isrc","-Isrc/ext-pexact","-Isrc/sat/bsat","-I../../tools","-I../reference/src",
        "-c",os.path.relpath(out/"pexact.c",abc),"-o",os.path.relpath(out/"pexact.o",abc)],cwd=abc,check=True)
    obj=out/"closure_bridge.o"
    subprocess.run(["g++","-O3","-std=c++17","-c",os.path.relpath(HERE/"closure_bridge.cpp",abc),
                    "-o",os.path.relpath(obj,abc)],cwd=abc,check=True)
    objects=(old/"objects.rsp").read_text().splitlines()
    def entry(path):
        return '"'+Path(os.path.relpath(path,abc)).as_posix()+'"'
    previous=entry(old/"pexact.o")
    if objects.count(previous)!=1:
        raise ValueError("Prepare the frozen symmetry executable against the same ABC object tree")
    objects[objects.index(previous)]=entry(out/"pexact.o")
    objects.append(entry(obj))
    rsp=out/"objects.rsp"
    rsp.write_text("\n".join(objects)+"\n",encoding="utf-8")
    binary=out/("abc.exe" if os.name=="nt" else "abc")
    subprocess.run(["g++","-o",os.path.relpath(binary,abc),"@"+os.path.relpath(rsp,abc),*libs],cwd=abc,check=True)
    print(sha256(binary.read_bytes()).hexdigest())


if __name__=="__main__":
    main()
