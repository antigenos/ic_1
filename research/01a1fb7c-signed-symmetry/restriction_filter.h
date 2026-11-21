/* First-gate conditional lower bounds for the four-input switching objective. */
#include "restriction_table.h"

typedef struct {
    int hi, lo, op, cost[5];
} RestrictionGate;

static RestrictionGate restriction_gates[30];
static int restriction_global[5];

static unsigned restriction_project(unsigned f, const unsigned rows[8])
{
    unsigned value = 0;
    for (int i = 0; i < 8; ++i)
        value |= ((f >> rows[i]) & 1u) << i;
    return (value & 1u ? value ^ 255u : value) >> 1;
}

static void restriction_prepare(unsigned target)
{
    static int previous = -1;
    if ((int)target == previous) return;
    previous = (int)target;
    const unsigned pins[] = {0xaaaa,0xcccc,0xf0f0,0xff00};
    const int ops[] = {2,4,6,8,14};
    unsigned functions[30];
    int charges[30], count = 0;
    memset(restriction_global,0,sizeof(restriction_global));
    for (int hi = 1; hi < 4; ++hi) for (int lo = 0; lo < hi; ++lo) {
        unsigned a = pins[hi], b = pins[lo];
        unsigned values[] = {a & ~b,b & ~a,a ^ b,a & b,a | b};
        for (int j = 0; j < 5; ++j) {
            RestrictionGate g = {.hi=hi,.lo=lo,.op=ops[j]};
            int ones = __builtin_popcount(values[j]);
            charges[count] = 2 * ones * (16-ones);
            functions[count] = values[j];
            restriction_gates[count++] = g;
        }
    }
    for (unsigned mask = 1; mask < 16; ++mask) {
        if (__builtin_popcount(mask) > 2) continue;
        unsigned pivot = 1;
        while ((pivot << 1) <= mask) pivot <<= 1;
        unsigned rows[2][8];
        for (unsigned i = 0; i < 8; ++i) {
            unsigned base = (i & (pivot-1)) | ((i & ~(pivot-1)) << 1);
            unsigned phase = __builtin_parity(base & mask);
            rows[0][i] = base | (phase ? pivot : 0);
            rows[1][i] = rows[0][i] ^ pivot;
        }
        unsigned t0 = restriction_project(target,rows[0]), t1 = restriction_project(target,rows[1]);
        for (int k = 0; k < 5; ++k) {
            int total = 2*(restriction_cost[0][k][t0]+restriction_cost[0][k][t1]);
            if (total > restriction_global[k]) restriction_global[k] = total;
        }
        for (int j = 0; j < count; ++j) {
            unsigned f0 = restriction_free[restriction_project(functions[j],rows[0])];
            unsigned f1 = restriction_free[restriction_project(functions[j],rows[1])];
            for (int k = 0; k < 5; ++k) {
                int total = charges[j] + 2*(restriction_cost[f0][k][t0]+restriction_cost[f1][k][t1]);
                if (total > restriction_gates[j].cost[k]) restriction_gates[j].cost[k] = total;
            }
        }
    }
}

static int restriction_window(PexaMan_t *p, int budget, int emit)
{
    const char *mode = getenv("REPLAY_RESTRICTION");
    if (!mode || p->nVars != 4 || p->nNodes < 2 || p->pPars->fOnlyAnd) return 1;
    int unlimited = !strcmp(mode,"cost");
    int global_only = !strcmp(mode,"global");
    if (!unlimited && !global_only && strcmp(mode,"size")) return 1;
    restriction_prepare((unsigned)p->pTruth[0] & 65535u);
    int k = unlimited || p->nNodes >= 6 ? 4 : p->nNodes-2;
    int global_k = k < 4 ? k+1 : 4;
    if (restriction_global[global_k] > budget) return 0;
    if (global_only) return 1;
    int available = 0;
    for (int j = 0; j < 30; ++j) {
        RestrictionGate *g = &restriction_gates[j];
        if (g->cost[k] <= budget) {
            ++available;
        } else if (emit) {
            int c[5] = {Abc_Var2Lit(p->VarMarks[4][0][g->hi],1),
                        Abc_Var2Lit(p->VarMarks[4][1][g->lo],1)};
            for (int b = 0; b < 3; ++b)
                c[2+b] = Abc_Var2Lit(1+b,(g->op >> (1+b)) & 1);
            if (!sat_solver_addclause(p->pSat,c,c+5)) return 0;
        }
    }
    return available > 0;
}
