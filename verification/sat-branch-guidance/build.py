"""Link two variants using the unchanged objects of a prepared, frozen Windows joint build."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REF = Path(sys.argv[1]).resolve()
ABC = REF / '.local/abc'
BASE = REF / '.local/variants/joint'
OUT = HERE / '.local'
os.environ['PATH'] = r'C:\msys64\ucrt64\bin' + os.pathsep + os.environ['PATH']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def edit(source, old, new):
    if source.count(old) != 1:
        raise ValueError(old)
    return source.replace(old, new)

def compile_unit(dest, filename):
    subprocess.run(['gcc', '-std=gnu11', '-O2', '-DABC_USE_STDINT_H=1', '-DABC_USE_CUDD=1',
                    '-DWIN32_NO_DLL', '-DSIZEOF_VOID_P=8', '-DSIZEOF_LONG=4', '-DSIZEOF_INT=4',
                    '-Isrc', '-Isrc/ext-pexact', '-Isrc/sat/bsat', '-I' + str(ROOT/'tools'),
                    '-I../reference/src', '-I'+str(HERE), '-c', str(dest/(filename+'.c')),
                    '-o', str(dest/(filename+'.o'))], cwd=ABC, check=True)

def assemble(diag):
    name = 'audit' if diag else 'conditional'
    dest = OUT/name
    dest.mkdir(parents=True, exist_ok=True)
    hdr = (ROOT/'tools/joint_trail.h').read_text()
    hook = '    replay_at_fixpoint = replay_visit;'
    begin = '    if (should_guide(p,q->target)) give_advice(p);\n'
    first = '#include "guidance.h"\n'
    if diag:
        first += '#include <windows.h>\nextern int guide_first_conflict;\n'
        hdr = edit(hdr, 'static ReplayQuery replay_query;', 'static ReplayQuery replay_query;\nstatic int first_joint;')
        hdr = edit(hdr, 'if (q->trace) {', 'if (first_joint < 0) first_joint = (int)s->stats.decisions;\n    if (q->trace) {')
        begin = '''    char mode = getenv("GUIDE_AUDIT_ARM")[0];
    LARGE_INTEGER t0,t1,t2,freq;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&t0);
    int enabled = mode == 'B' || (mode == 'C' && should_guide(p,q->target));
    QueryPerformanceCounter(&t1);
    if (enabled) give_advice(p);
    QueryPerformanceCounter(&t2);
    first_joint = guide_first_conflict = -1;
'''
        hdr = edit(hdr, '    replay_at_fixpoint = NULL;', r'''    printf("QUERY gates=%d cap=%d enabled=%d result=%d decisions=%lld conflicts=%lld first_joint=%d first_conflict=%d feature_ticks=%lld injection_ticks=%lld hz=%lld\n",p->nNodes,bound,enabled,result,(long long)p->pSat->stats.decisions,(long long)p->pSat->stats.conflicts,first_joint,guide_first_conflict,t1.QuadPart-t0.QuadPart,t2.QuadPart-t1.QuadPart,freq.QuadPart);
    replay_at_fixpoint = NULL;''')
        sat = (BASE/'satSolver.c').read_text()
        sat = edit(sat, '#include "trail_clause.h"', '#include "trail_clause.h"\nint guide_first_conflict;')
        sat = edit(sat, 's->stats.conflicts++; conflictC++;', 'if (guide_first_conflict < 0) guide_first_conflict = (int)s->stats.decisions;\n            s->stats.conflicts++; conflictC++;')
        (dest/'satSolver.c').write_text(sat)
        compile_unit(dest,'satSolver')
    hdr = edit(hdr, 'static int replay_solve(', first+'static int replay_solve(')
    (dest/'joint_trail.h').write_text(edit(hdr, hook, begin+hook))
    shutil.copyfile(BASE/'pexact.c', dest/'pexact.c')
    compile_unit(dest,'pexact')
    rsp = (BASE/'objects.rsp').read_text()
    for unit in (['pexact','satSolver'] if diag else ['pexact']):
        rsp = edit(rsp, '../variants/joint/'+unit+'.o', (dest/(unit+'.o')).as_posix())
    (dest/'objects.rsp').write_text(rsp)
    binary = dest/'abc.exe'
    subprocess.run(['g++','-o',str(binary),'@'+str(dest/'objects.rsp'),'-lm','-lws2_32','-lpsapi','-lshlwapi'],cwd=ABC,check=True)
    return sha(binary)

if __name__ == '__main__':
    assert sha(BASE/'abc.exe') == '8a9b38bb96df8f8b1a74b9a73e30dd692958de8d6b46d87011710630df89ce6d'
    assert sha(REF/'.local/variants/screen-guide/abc.exe') == '1529810005e9c8ab491f4e3aa859da6e14989535f21e531ed4f724bdab259865'
    hashes = {m:assemble(m=='audit') for m in ('conditional','audit')}
    print(json.dumps(hashes))
