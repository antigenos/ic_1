#include "cofactor.h"

static int ff_cofactor_search(ReplayQuery *q)
{
    PexaMan_t *p = q->p;
    sat_solver *solver = p->pSat;
    if (p->nVars != 4 || p->nNodes < 2)
        return sat_solver_solve(solver, NULL, NULL, 0, 0, 0, 0);
    static FfRestrictions cuts;
    static FfBounds bounds;
    static int ready = 0;
    static int links_ready = 0;
    static unsigned last_target = UINT_MAX;
    if (!ready) {
        ff_init_restrictions(&cuts);
        ready = 1;
    }
    const char *mode = getenv("FF_MODE");
    int whole_only = mode && !strcmp(mode, "cofactor-whole");
    int audit = getenv("FF_COFACTOR_AUDIT") != NULL;
    if (last_target != q->target) {
        bounds.whole = ff_target_bound(&cuts, q->target);
        last_target = q->target;
        links_ready = 0;
    }
    if (bounds.whole > q->bound) {
        if (audit) {
            int status = sat_solver_solve(solver, NULL, NULL, 0, 0, 0, 0);
            printf("FF_COF whole upper=%d lower=%d status=%d\n", q->bound, bounds.whole, status);
            if (status != l_False) abort();
        }
        return l_False;
    }
    if (!whole_only && !links_ready) {
        ff_connection_bounds(&cuts, q->target, &bounds);
        links_ready = 1;
    }
    if (audit && !whole_only) {
        for (int pi = 0; pi < 4; ++pi) {
            if (bounds.primary[pi] <= q->bound) continue;
            lit select = Abc_Var2Lit(p->VarMarks[p->nObjs-1][1][pi], 0);
            int status = sat_solver_solve(solver, &select, &select + 1, 0, 0, 0, 0);
            printf("FF_COF pi=%d upper=%d lower=%d status=%d\n", pi, q->bound, bounds.primary[pi], status);
            if (status != l_False) abort();
        }
    }
    if (!whole_only) {
        for (int pi = 0; pi < 4; ++pi) {
            if (bounds.primary[pi] <= q->bound) continue;
            lit exclude = Abc_Var2Lit(p->VarMarks[p->nObjs-1][1][pi], 1);
            if (!sat_solver_addclause(solver, &exclude, &exclude + 1)) return l_False;
        }
    }
    return sat_solver_solve(solver, NULL, NULL, 0, 0, 0, 0);
}
