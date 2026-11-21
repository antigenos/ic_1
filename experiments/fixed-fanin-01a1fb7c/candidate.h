#include "projection.h"

static int ff_implies(sat_solver *s, int selector, int variable, int required)
{
    lit clause[2] = {Abc_Var2Lit(selector, 1), Abc_Var2Lit(variable, !required)};
    return sat_solver_addclause(s, clause, clause+2);
}

static int ff_add_clauses(ReplayQuery *q)
{
    PexaMan_t *p = q->p;
    const char *mode = getenv("FF_MODE");
    if (p->nNodes < 2 || (mode && !strcmp(mode,"off"))) return 1;
    int with_ops = !mode || !strcmp(mode,"all") || !strcmp(mode,"ops");
    int with_margins = !mode || !strcmp(mode,"all") || !strcmp(mode,"margins");
    if (!with_ops && !with_margins) abort();
    const unsigned codes[5] = {2,4,6,8,14};
    int out = p->nObjs - 1, partner = out - 1;
    for (int pi = 0; pi < p->nVars; ++pi) {
        unsigned h = 0;
        for (int r = 1; r < q->rows; ++r) h |= ((r >> pi) & 1u) << r;
        FfProjection result = ff_project(q->rows,q->target,h);
        int selector = p->VarMarks[out][1][pi];
        if (!result.operators) {
            lit unit = Abc_Var2Lit(selector,1);
            if (!sat_solver_addclause(p->pSat,&unit,&unit+1)) return 0;
            continue;
        }
        if (with_ops) {
            unsigned all = 15, any = 0;
            for (int k = 0; k < 5; ++k) if (result.operators & (1u<<k)) {
                all &= codes[k];
                any |= codes[k];
            }
            for (int b = 1; b <= 3; ++b) if (!((all ^ any) & (1u<<b))) {
                int var = 3*(p->nNodes-1) + b;
                if (!ff_implies(p->pSat,selector,var,(all>>b)&1u)) return 0;
            }
        }
        if (!with_margins) continue;
        for (int r = 1; r < q->rows; ++r) if ((result.zero | result.one) & (1u<<r)) {
            int var = replay_row_var(p,partner,r);
            if (!ff_implies(p->pSat,selector,var,(result.one>>r)&1u)) return 0;
        }
        for (int a = 1; a <= q->rows/2; ++a) if (!(result.counts & (1u<<a))) {
            int var = replay_count_var(p,partner,q->rows,a);
            if (!ff_implies(p->pSat,selector,var,0)) return 0;
        }
    }
    return 1;
}
