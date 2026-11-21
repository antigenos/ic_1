#include "gate_clauses.h"

static int ff_add_native(void *s, int *clause, int n)
{
    return sat_solver_addclause((sat_solver *)s,clause,clause+n);
}

static int ff_add_types(ReplayQuery *q)
{
    PexaMan_t *p = q->p;
    if (p->nNodes < 2) return 1;
    const char *mode = getenv("FF_MODE");
    int types[5], out=p->nObjs-1;
    for (int k=0;k<5;++k) types[k]=sat_solver_addvar(p->pSat);
    if (!ff_define_types(p->pSat,ff_add_native,types,1+3*(p->nNodes-1))) return 0;
    if (mode && !strcmp(mode,"types-only")) return 1;
    for (int r=1;r<q->rows;++r) {
        int high=replay_row_var(p,out-1,r), low=replay_row_var(p,out,r)-1;
        if (!ff_type_row(p->pSat,ff_add_native,types,high,low,(q->target>>r)&1)) return 0;
    }
    return 1;
}
