#include "xor_condition.h"

static int ff_xor_search(ReplayQuery *q)
{
    PexaMan_t *p=q->p;
    sat_solver *s=p->pSat;
    if (p->nNodes<2 || !ff_only_xor(q->target,p->nVars))
        return sat_solver_solve(s,NULL,NULL,0,0,0,0);
    const char *mode=getenv("FF_MODE");
    int use_units=!mode || strcmp(mode,"xor-only");
    int audit=getenv("FF_PROOF_AUDIT")!=NULL;
    int gate_bits=1+3*(p->nNodes-1);
    lit assumptions[3], blocker[3];
    for (int b=0;b<3;++b) {
        assumptions[b]=Abc_Var2Lit(gate_bits+b,!((6>>(b+1))&1));
        blocker[b]=Abc_LitNot(assumptions[b]);
    }
    int status=sat_solver_solve(s,assumptions,assumptions+3,0,0,0,0);
    if (status==l_True) return status;
    if (status!=l_False) return sat_solver_solve(s,NULL,NULL,0,0,0,0);
    if (audit && use_units) {
        for (int pi=0;pi<p->nVars;++pi) {
            lit select=Abc_Var2Lit(p->VarMarks[p->nObjs-1][1][pi],0);
            int check=sat_solver_solve(s,&select,&select+1,0,0,0,0);
            printf("FF_PROOF gates=%d bound=%d pi=%d status=%d\n",p->nNodes,q->bound,pi,check);
            if (check!=l_False) abort();
        }
    }
    if (!sat_solver_addclause(s,blocker,blocker+3)) return l_False;
    if (use_units) for (int pi=0;pi<p->nVars;++pi) {
        lit unit=Abc_Var2Lit(p->VarMarks[p->nObjs-1][1][pi],1);
        if (!sat_solver_addclause(s,&unit,&unit+1)) return l_False;
    }
    return sat_solver_solve(s,NULL,NULL,0,0,0,0);
}
