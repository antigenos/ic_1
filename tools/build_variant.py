"""Build a pinned-plugin variant while keeping the linked author executable intact."""
import argparse
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ABC = ROOT / ".local/abc"


def build(name, patches):
    if not re.fullmatch(r"[a-z0-9_-]+", name):
        raise ValueError("Expected a simple variant name")
    dest = ROOT / ".local/variants" / name
    dest.mkdir(parents=True, exist_ok=True)
    plugin = ABC / "src/ext-pexact"
    shutil.copyfile(plugin / "pexact.c", dest / "pexact.c")
    for patch in patches:
        subprocess.run(["git", "-c", "apply.whitespace=nowarn", "apply",
                        "--directory=" + dest.relative_to(ROOT).as_posix(),
                        str(patch.resolve())], cwd=ROOT, check=True)
    if sys.platform == "win32":
        flags = ["-DWIN32_NO_DLL", "-DSIZEOF_VOID_P=8", "-DSIZEOF_LONG=4",
                 "-DSIZEOF_INT=4"]
        objects = (ABC / "abc-win-objects.rsp").read_text().split()
        libs = ["-lm", "-lws2_32", "-lpsapi", "-lshlwapi"]
        suffix = ".exe"
    else:
        # Use the pinned Makefile's own module inventory and compiler options.
        info = subprocess.check_output(["make", "-s", "cmake_info", "ABC_MAKE_NO_DEPS=1"],
                                       cwd=ABC, text=True)
        def field(key):
            return info.split("SEPARATOR_" + key)[1].strip().split()
        flags = field("CFLAGS")
        objects = [str(Path(f).with_suffix(".o")) for f in field("SRC")]
        libs = field("LIBS")
        suffix = ""
    subprocess.run(["gcc", "-std=gnu11", "-O2", "-DABC_USE_STDINT_H=1", "-DABC_USE_CUDD=1",
                    *flags, "-Isrc", "-Isrc/ext-pexact", "-I../../tools",
                    "-c", os.path.relpath(dest / "pexact.c", ABC),
                    "-o", os.path.relpath(dest / "pexact.o", ABC)], cwd=ABC, check=True)
    obj = "src/ext-pexact/pexact.o"
    if objects.count(obj) != 1:
        raise ValueError("Unexpected plugin object inventory")
    objects[objects.index(obj)] = '"' + Path(os.path.relpath(dest / "pexact.o", ABC)).as_posix() + '"'
    rsp = dest / "objects.rsp"
    rsp.write_text("\n".join(objects) + "\n", encoding="utf-8")
    binary = dest / ("abc" + suffix)
    subprocess.run(["g++", "-o", os.path.relpath(binary, ABC), "@" + os.path.relpath(rsp, ABC),
                    *libs], cwd=ABC, check=True)
    print(binary)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("name")
    p.add_argument("patches", nargs="+", type=Path)
    args = p.parse_args()
    build(args.name, args.patches)
