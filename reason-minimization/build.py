"""Build only changed units against a read-only prepared frozen Windows checkout."""
from pathlib import Path
import os, sys, subprocess, hashlib, json, shutil
D = Path(__file__).resolve().parent
ROOT = D.parent
sys.path.insert(0, str(ROOT/"tools"))
from build_candidate_screen import replace_once as rep
REF = Path(os.environ.get("TCJAP_REFERENCE", ROOT.parent/"tcjap-replay")).resolve()
CACHE = ROOT/".local/reason"
GCC = Path("C:/msys64/ucrt64/bin")
os.environ["PATH"] = str(GCC) + os.pathsep + os.environ["PATH"]
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def build(role, diag):
    frozen = REF/".local/variants"/("screen-short" if role=="short" else "joint")
    abc = REF/".local/abc"
    dst = CACHE/(role+("-diag" if diag else ""))
    dst.mkdir(parents=True,exist_ok=True)
    base = (ROOT/"tools/joint_trail.h").read_text()
    src = (frozen/"joint_trail.h").read_text() if role=="short" else base
    assert sha(frozen/"pexact.c").lower()=="d679ec5d3797db6e506feee4dfef89fb635bf8f717000461585bd7702b660f29"
    assert sha(frozen/"satSolver.c").lower()=="fcbae7e97c2b10d1d6e2e0f2ebbdb3e22267a4ef6235397b9bdf73ef353365c6"
    for f in ["pexact.c","satSolver.c"]:
        shutil.copyfile(frozen/f,dst/f)
    if role=="online":
        src = rep(src,"int victim, ReplaySignal *signals)","int victim, ReplaySignal *signals, int victim_obj)")
        src = rep(src,"selector, signals))","selector, signals, -1))")
        src = rep(src,"var, signals))","var, signals, obj[k]))")
        start = src.index("    for (int j = p->nVars; j < out; ++j) {",src.index("static int replay_explain"))
        end = src.index("    if (q->trace)",start)
        src = src[:start]+(D/"project_counts.c.inc").read_text()+"\n"+src[end:]
    sat = (dst/"satSolver.c").read_text()
    if diag:
        src = rep(src,"static ReplayQuery replay_query;", """static ReplayQuery replay_query;
extern long long rm_tick(void), rm_frequency(void);
static long long rm_ticks[2], rm_tries[2], rm_fallback[2];
static void rm_finish_attempt(int edge,long long start,int fallback){
    rm_ticks[edge] += rm_tick()-start;
    rm_tries[edge]++; rm_fallback[edge]+=fallback;
}""")
        src = rep(src,"    int clause[","    long long started = rm_tick();\n    int clause[")
        if role!="online":
            src=rep(src,"    if (!replay_imply(s, clause, size)) return 0;","    int accepted=replay_imply(s,clause,size);\n    rm_finish_attempt(unselected_pin>=0,started,0);\n    if(!accepted) return 0;")
        src=rep(src,"    replay_at_fixpoint = replay_visit;", """    memset(rm_ticks,0,sizeof(rm_ticks)); memset(rm_tries,0,sizeof(rm_tries));
    memset(rm_fallback,0,sizeof(rm_fallback)); if(q->trace) puts("QUERY");
    replay_at_fixpoint = replay_visit;""")
        src=rep(src,"    replay_at_fixpoint = NULL;", """    replay_at_fixpoint = NULL;
    printf("WORK %lld %lld %lld %lld %lld %lld %lld %lld %lld %lld\\n",
        (long long)p->pSat->stats.conflicts,(long long)p->pSat->stats.decisions,
        (long long)p->pSat->stats.propagations,rm_tries[0],rm_tries[1],rm_ticks[0],rm_ticks[1],
        rm_frequency(),rm_fallback[0],rm_fallback[1]);""")
        trail=(ROOT/"tools/trail_clause.h").read_text()
        trail=rep(trail,"    check(sat_solver_enqueue", '    if(getenv("REPLAY_TRACE")) printf("HANDLE %d\\n",reason);\n    check(sat_solver_enqueue')
        (dst/"trail_clause.h").write_text(trail)
        sat=rep(sat,"    return hConfl;", """    if(hConfl && replay_at_fixpoint && getenv("REPLAY_TRACE")){
        clause *c=clause_read(s,hConfl);
        printf("CLASH %d",hConfl==s->hBinary ? -1 : hConfl);
        for(int t=0;t<clause_size(c);++t){
            int literal=clause_begin(c)[t];
            if(var_value(s,lit_var(literal)) != !lit_sign(literal)) abort();
            printf(" %d",literal);
        }
        puts("");
    }
    return hConfl;""")
        sat=rep(sat,"    // update reasons", """    if(replay_at_fixpoint && getenv("REPLAY_TRACE")){
        puts("GC");
        Sat_MemForEachLearned(pMem,c,i,k) if(!c->mark)
            printf("MOVE %d %d\\n",Sat_MemHand(pMem,i,k),clause_id(c));
        puts("ENDGC");
    }
    // update reasons""")
    (dst/"satSolver.c").write_text(sat)
    (dst/"joint_trail.h").write_text(src)
    flags = ["-std=gnu11","-O2","-DABC_USE_STDINT_H=1","-DABC_USE_CUDD=1","-DWIN32_NO_DLL",
             "-DSIZEOF_VOID_P=8","-DSIZEOF_LONG=4","-DSIZEOF_INT=4","-Isrc","-Isrc/ext-pexact",
             "-Isrc/sat/bsat","-I"+str(ROOT/"tools"),"-I"+str(REF/".local/reference/src")]
    units=["pexact","satSolver"] if diag else ["pexact"]
    if diag:
        flags.append("-DRM_DIAG")
        (dst/"timer.c").write_text('#include <windows.h>\nlong long rm_tick(void){LARGE_INTEGER v; QueryPerformanceCounter(&v);return v.QuadPart;}\nlong long rm_frequency(void){LARGE_INTEGER v;QueryPerformanceFrequency(&v);return v.QuadPart;}\n')
        units.append("timer")
    for unit in units:
        subprocess.run(["gcc",*flags,"-c",dst/(unit+".c"),"-o",dst/(unit+".o")],cwd=abc,check=True)
    objects=(frozen/"objects.rsp").read_text().splitlines()
    for unit in units:
        entry='"'+(dst/(unit+".o")).as_posix()+'"'
        if unit=="timer":
            objects.append(entry)
        else:
            idx, = [i for i,x in enumerate(objects) if x.endswith("/"+unit+'.o"')]
            objects[idx]=entry
    rsp=dst/"objects.rsp"
    rsp.write_text("\n".join(objects)+"\n",encoding="utf-8")
    subprocess.run(["g++","-o",dst/"abc.exe","@"+str(rsp),"-lm","-lws2_32","-lpsapi","-lshlwapi"],cwd=abc,check=True)
    return sha(dst/"abc.exe")

if __name__=="__main__":
    for role,diag in [("online",False),("online",True),("joint",True),("short",True)]:
        print(role,diag,build(role,diag),flush=True)
