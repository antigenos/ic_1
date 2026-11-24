"""Relink the preserved author/TCJAP binary using its original objects and one replacement unit."""
from hashlib import sha256
import os
import platform
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ABC = ROOT/'.local/abc'
BASE = ROOT/'.local/variants/orbit-signed'
DEST = ROOT/'.local/variants/orbit-frontier-complete'
ANCHOR = '''    int maxGateCount = MAJ_NOBJS - p->nVars;

    while ( r < maxGateCount )'''
HOOK = '''    int maxGateCount = MAJ_NOBJS - p->nVars;
    const char *frontierCap = getenv("PEXACT_FRONTIER_CAP");
    if (frontierCap && *frontierCap && pPars->nVars == 4 && !pPars->fOnlyAnd) {
        char *end = NULL;
        long cap = strtol(frontierCap,&end,10);
        if (end != frontierCap && !*end && cap >= 0 && cap <= INT_MAX) {
            unsigned short wires[MAJ_NOBJS];
            int count = -1;
            const char *mode = getenv("PEXACT_FRONTIER_MODE");
            int projected = !mode || strcmp(mode,"uniform") != 0;
            act = frontier_bound((unsigned)pTruth[0] & 65535u, (int)cap, projected,
                                 wires, MAJ_NOBJS, &count);
            if (getenv("PEXACT_FRONTIER_TRACE"))
                printf("FRONTIER lower=%d paid_wires=%d projected=%d\\n",act,count,projected);
            if (count > 0 && count+1 < maxGateCount) {
                int savedNodes = pPars->nNodes;
                pPars->nNodes = count+1;
                PexaMan_t *trial = PexaManAlloc(pPars,pTruth);
                int verified = trial && frontier_verify(trial,pPars,wires,count,act);
                if (verified) {
                    PexaManPrintSolution(trial,fCompl,true);
                    Abc_PrintTime(1,"Total runtime",Abc_Clock()-clkTotal);
                }
                if (trial) PexaManFree(trial);
                if (verified) { PexaManFree(p); return 0; }
                pPars->nNodes = savedNodes;
            }
        }
    }

    while ( r < maxGateCount )'''


def build():
    DEST.mkdir(parents=True,exist_ok=True)
    src=(BASE/'pexact.c').read_text()
    # This same block also occurs in an older mode; change only the binary-mode implementation.
    marker='int PexaManExactPowerSynthesisBasePowerBDDBinary( Bmc_EsPar_t * pPars, const int stepSize )'
    head, tail=src.split(marker)
    if tail.count(ANCHOR)!=1:
        raise ValueError('unexpected mode-2 implementation')
    (DEST/'pexact.c').write_text(head+'#include <limits.h>\n#include "bridge.h"\n'+marker+tail.replace(ANCHOR,HOOK))
    if os.name=='nt':
        flags=['-DWIN32_NO_DLL','-DSIZEOF_VOID_P=8','-DSIZEOF_LONG=4','-DSIZEOF_INT=4']
        libs=['-lm','-lws2_32','-lpsapi','-lshlwapi']
    else:
        info=subprocess.check_output(['make','-s','cmake_info','ABC_MAKE_NO_DEPS=1'],cwd=ABC,text=True)
        flags=info.split('SEPARATOR_CFLAGS')[1].strip().split()
        libs=info.split('SEPARATOR_LIBS')[1].strip().split()
    def run(command):
        subprocess.run(command,cwd=ABC,check=True)
    def rel(path):
        return os.path.relpath(path,ABC)
    run(['gcc','-std=gnu11','-O2','-DABC_USE_STDINT_H=1','-DABC_USE_CUDD=1',*flags,
         '-Isrc','-Isrc/ext-pexact','-Isrc/sat/bsat','-I../../tools','-I../reference/src',
         '-I'+rel(BASE),'-I'+rel(HERE),'-c',rel(DEST/'pexact.c'),'-o',rel(DEST/'pexact.o')])
    arch=['-march=x86-64-v2'] if platform.machine().lower() in ('amd64','x86_64') else []
    run(['g++','-std=c++20','-O3','-DNDEBUG',*arch,'-c',rel(HERE/'bridge.cpp'),'-o',rel(DEST/'bridge.o')])
    rsp=(BASE/'objects.rsp').read_text()
    key='../variants/orbit-signed/pexact.o'
    if rsp.count(key)!=1:
        raise ValueError('unexpected object list')
    rsp=rsp.replace(key,f'../variants/{DEST.name}/pexact.o')+f'\n"../variants/{DEST.name}/bridge.o"\n'
    (DEST/'objects.rsp').write_text(rsp)
    binary=DEST/('abc.exe' if os.name=='nt' else 'abc')
    run(['g++','-o',rel(binary),'@'+rel(DEST/'objects.rsp'),*libs])
    print(binary,sha256(binary.read_bytes()).hexdigest())


if __name__=='__main__':
    build()
