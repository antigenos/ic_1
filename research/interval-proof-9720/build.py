"""Build only the changed pexact translation unit against the frozen joint variant."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
SOURCE_SHA = "d679ec5d3797db6e506feee4dfef89fb635bf8f717000461585bd7702b660f29"


def replace_one(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Unexpected frozen source around " + old[:72])
    return source.replace(old, new)


def generate(source):
    start = "        PexaMan_t * next = PexaManAlloc( pPars, pTruth );"
    source = replace_one(source, start, "        abctime begin_window = Abc_Clock();\n" + start)
    solve = "        int status = replay_solve(*p, node.act + *delta);"
    before_solve = """        if ( !ExactPowerSynthesisCnfBddRange( pPars, *p, &node, *delta ) )
        {
            continue;
        }
"""
    trace = ('            if (getenv("OPTWIN_TRACE")) printf("WINDOW r=%d lo=%d hi=%d '
             'state=build seconds=%.6f\\n", rIt, node.act, node.act + *delta, '
             '(double)(Abc_Clock() - begin_window) / CLOCKS_PER_SEC);\n')
    source = replace_one(source, before_solve + solve,
                         before_solve.replace("            continue;", trace + "            continue;") + solve)
    after = ('\n        if (getenv("OPTWIN_TRACE")) printf("WINDOW r=%d lo=%d hi=%d '
             'state=%d seconds=%.6f\\n", rIt, node.act, node.act + *delta, status, '
             '(double)(Abc_Clock() - begin_window) / CLOCKS_PER_SEC);')
    source = replace_one(source, solve, solve + after)
    entry = '#include "joint_trail.h"'
    source = replace_one(source, entry, entry + '\n#include "window_proof.h"')
    inner = "int PexaManExactPowerSynthesisBasePowerBDDBinaryInner( Bmc_EsPar_t * pPars,"
    source = replace_one(source, inner, inner.replace("( ", "( WindowProof *w, "))
    scope = "    int delta = stepSize;"
    source = replace_one(source, scope, scope + "\n    WindowProof study;\n    window_init(&study, pPars->nVars);")
    call = "PexaManExactPowerSynthesisBasePowerBDDBinaryInner( pPars, &p,"
    source = replace_one(source, call, call.replace("( pPars", "( &study, pPars"))
    timer = "        abctime begin_window = Abc_Clock();"
    test = """        if (window_skip(w, rIt, node.act, node.act + *delta)) {
            if (w->trace) printf("WINDOW r=%d lo=%d hi=%d state=skip seconds=0\\n",
                                 rIt, node.act, node.act + *delta);
            continue;
        }
"""
    source = replace_one(source, timer, test + timer.replace("Abc_Clock();","w->trace ? Abc_Clock() : 0;"))
    source = source.replace('if (getenv("OPTWIN_TRACE")) printf', 'if (w->trace) printf')
    return replace_one(source, solve, solve + "\n        if (status == l_False) window_unsat(w, rIt, node.act, node.act + *delta);")


def build(baseline):
    abc = baseline / ".local/abc"
    joint = baseline / ".local/variants/joint"
    dest = HERE / ".local/build"
    dest.mkdir(exist_ok=True, parents=True)
    original = (joint / "pexact.c").read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA:
        raise ValueError("Build the pinned joint variant first, see root REPRODUCTION.md")
    (dest / "pexact.c").write_text(generate(original.decode()), encoding="utf8")
    def rel(p):
        return Path(os.path.relpath(p, abc)).as_posix()
    if os.name == "nt":
        flags = ["-DWIN32_NO_DLL", "-DSIZEOF_VOID_P=8", "-DSIZEOF_LONG=4", "-DSIZEOF_INT=4"]
        libs = ["-lm", "-lws2_32", "-lpsapi", "-lshlwapi"]
    else:
        info = subprocess.check_output(["make", "-s", "cmake_info", "ABC_MAKE_NO_DEPS=1"],
                                       cwd=abc, text=True)
        flags = info.split("SEPARATOR_CFLAGS")[1].strip().split()
        libs = info.split("SEPARATOR_LIBS")[1].strip().split()
    source, obj = rel(dest/"pexact.c"), rel(dest/"pexact.o")
    subprocess.run(["gcc","-std=gnu11","-O2","-DABC_USE_STDINT_H=1","-DABC_USE_CUDD=1",
                    *flags,"-Isrc","-Isrc/ext-pexact","-Isrc/sat/bsat","-I../../tools",
                    "-I../reference/src","-I"+rel(HERE),"-c",source,"-o",obj], cwd=abc, check=True)
    response = replace_one((joint/"objects.rsp").read_text(), '"../variants/joint/pexact.o"', '"'+obj+'"')
    (dest/"objects.rsp").write_text(response, encoding="utf8")
    binary = dest / ("abc.exe" if os.name == "nt" else "abc")
    subprocess.run(["g++","-o",rel(binary),"@"+rel(dest/"objects.rsp"),*libs], cwd=abc, check=True)
    print(hashlib.sha256(binary.read_bytes()).hexdigest(), binary)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline", type=Path, help="Frozen reproduction checkout with built joint variant")
    build(ap.parse_args().baseline.resolve())
