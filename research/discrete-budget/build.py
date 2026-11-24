"""Rebuild pexact only, using pinned, read-only joint objects and the common outer filter."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTER = "5400328802c98c1870fb7f61ff2475f698ee48ea"
PREFIX = "research/interval-proof-9720/"
FROZEN = "d679ec5d3797db6e506feee4dfef89fb635bf8f717000461585bd7702b660f29"


def gitfile(path):
    return subprocess.check_output(["git","show",OUTER+":"+PREFIX+path], cwd=ROOT)


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Unexpected source anchor: "+old)
    return source.replace(old,new)


def make(base, mode, profile):
    abc = base / ".local/abc"
    joint = base / ".local/variants/joint"
    dest = HERE / ".local" / (mode + ("-profile" if profile else ""))
    dest.mkdir(parents=True, exist_ok=True)
    upstream = (joint/"pexact.c").read_bytes().replace(b"\r\n",b"\n")
    assert hashlib.sha256(upstream).hexdigest() == FROZEN
    definitions = {"__file__":str(dest/"outer_build.py"), "__name__":"outer_build"}
    exec(compile(gitfile("build.py"), "pinned_outer_build.py","exec"),definitions)
    source = definitions["generate"](upstream.decode())
    call = "int status = replay_solve(*p, node.act + *delta);"
    source = once(source,call,"screen_lower = node.act;\n        "+call)
    (dest/"window_proof.h").write_bytes(gitfile("window_proof.h"))
    trail = (ROOT/"tools/joint_trail.h").read_text()
    trail = once(trail,"static ReplayQuery replay_query;", "static ReplayQuery replay_query;\nstatic int screen_lower;")
    point = '    replay_at_fixpoint = replay_visit;'
    trail = once(trail,point,r'''    if (q->trace) printf("WINDOW_BOUND %d %d\n",screen_lower,bound);
'''+point)
    if mode != "joint":
        refine = (ROOT/"tools/screen_window_filter.h").read_text().replace("static int screen_lower;","")
        if mode == "trigger":
            # Rule lives in a separately committed file, frozen after development.
            guard=(HERE/"trigger.h").read_text()
            refine=once(refine, "    enum { words",guard+"\n    enum { words")
            refine=refine.replace("if (SCREEN_HOLES", "if (use_holes")
        if profile:
            refine=once(refine, "    int low=0", "    ++calls; long long dt=stamp();\n    int low=0")
            refine=once(refine, "    unsigned supported", "    domain_ticks+=stamp()-dt;\n    unsigned supported")
            refine=once(refine, "        P9JointResult fixed;", "        ++fixed_calls; long long kt=stamp();\n        P9JointResult fixed;")
            refine=once(refine, "        for (int b=1", "        kernel_ticks+=stamp()-kt;\n        for (int b=1")
            count_dp="++dp_builds;" if mode=="holes" else ("dp_builds+=use_holes;" if mode=="trigger" else "")
            refine=once(refine,"    ++calls;", "    "+count_dp+" ++calls;")
            refine=once(refine,"    if (lo<0)", "    ++membership;\n    if (lo<0)")
        (dest/"screen_window_filter.h").write_text(refine)
        trail=once(trail,"static int replay_pair(", "#define SCREEN_HOLES "+str(int(mode!="interval"))+'\n#include "screen_window_filter.h"\nstatic int replay_pair(')
        line="    screen_refine(q,signals,obj,unselected_pin,ops,zeros,ones,domains,cap,charged,&result);"
        trail=once(trail,"    if (unselected_pin >= 0) {",line+"\n    if (unselected_pin >= 0) {")
        trail=once(trail,"if (j != obj[0] && j != obj[1]) break;", "/* All remaining cost-domain exclusions are premises. */")
    if profile:
        start="#define DB_PROFILE 1\n#include <windows.h>\nstatic long long stamp(void){LARGE_INTEGER t; QueryPerformanceCounter(&t); return t.QuadPart;}\n"
        start+="static long long trigger_considered,trigger_ticks;\n"
        start+="static long long calls,dp_builds,fixed_calls,domain_ticks,kernel_ticks,reason_ticks,attempts,membership;\n"
        trail=start+trail
        key="    if (!replay_imply(s, clause, size)) return 0;"
        trail=once(trail, "    int clause[", "    ++attempts; long long start_reason=stamp();\n    int clause[")
        trail=once(trail,key,"    int admitted=replay_imply(s,clause,size);\n    reason_ticks+=stamp()-start_reason;\n    if (!admitted) return 0;")
        trail=once(trail,point, "    trigger_considered=trigger_ticks=calls=dp_builds=fixed_calls=domain_ticks=kernel_ticks=reason_ticks=attempts=membership=0;\n"+point)
        trail=once(trail,"    replay_at_fixpoint = NULL;", r'''    replay_at_fixpoint = NULL;
    LARGE_INTEGER freq; QueryPerformanceFrequency(&freq);
    printf("COST lo=%d hi=%d calls=%lld builds=%lld fixed=%lld membership=%lld domain_ticks=%lld kernel_ticks=%lld reason_ticks=%lld reason_attempts=%lld frequency=%lld decisions=%lld propagations=%lld trigger_considered=%lld trigger_ticks=%lld\n",
        screen_lower,bound,calls,dp_builds,fixed_calls,membership,domain_ticks,kernel_ticks,reason_ticks,attempts,freq.QuadPart,(long long)p->pSat->stats.decisions,(long long)p->pSat->stats.propagations,trigger_considered,trigger_ticks);''')
    (dest/"joint_trail.h").write_text(trail)
    (dest/"pexact.c").write_text(source)
    rel=lambda p: Path(os.path.relpath(p,abc)).as_posix()
    flags=["-std=gnu11","-O2","-DABC_USE_STDINT_H=1","-DABC_USE_CUDD=1","-DWIN32_NO_DLL",
           "-DSIZEOF_VOID_P=8","-DSIZEOF_LONG=4","-DSIZEOF_INT=4","-Isrc","-Isrc/ext-pexact","-Isrc/sat/bsat","-I../reference/src"]
    subprocess.run(["gcc",*flags,"-I"+rel(ROOT/"tools"),"-c",rel(dest/"pexact.c"),"-o",rel(dest/"pexact.o")],cwd=abc,check=True)
    rsp=once((joint/"objects.rsp").read_text(),'"../variants/joint/pexact.o"','"'+rel(dest/"pexact.o")+'"')
    (dest/"objects.rsp").write_text(rsp)
    subprocess.run(["g++","-o",rel(dest/"abc.exe"),"@"+rel(dest/"objects.rsp"),"-lm","-lws2_32","-lpsapi","-lshlwapi"],cwd=abc,check=True)
    print(mode,profile,hashlib.sha256((dest/"abc.exe").read_bytes()).hexdigest())


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("base",type=Path)
    ap.add_argument("modes",nargs="+",choices=("joint","interval","holes","trigger"))
    args=ap.parse_args()
    for mode in args.modes:
        for profile in (False,True):
            make(args.base.resolve(),mode,profile)
