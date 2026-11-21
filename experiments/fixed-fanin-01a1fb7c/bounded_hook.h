#include "bounded.h"

static int ff_full_support(unsigned truth)
{
    for (int i = 0; i < 4; ++i) {
        unsigned step = 1u << i;
        int changes = 0;
        for (unsigned row = 0; row < 16; ++row)
            if (!((row >> i) & 1u) && (((truth >> row) ^ (truth >> (row + step))) & 1u))
                changes = 1;
        if (!changes) return 0;
    }
    return 1;
}

static int ff_pin_circuit(PexaMan_t *p, const FfCertificate *cert)
{
    for (int i = 0; i < cert->gates; ++i) {
        FfGate g = cert->chain[i];
        int node = p->nVars + i;
        int hi = p->VarMarks[node][0][g.hi];
        int lo = p->VarMarks[node][1][g.lo];
        if (!hi || !lo) return 0;
        lit units[5] = {Abc_Var2Lit(hi, 0), Abc_Var2Lit(lo, 0)};
        for (int k = 0; k < 3; ++k)
            units[2+k] = Abc_Var2Lit(1 + 3*i + k, !((g.op >> (k+1)) & 1));
        for (int j = 0; j < 5; ++j)
            if (!sat_solver_addclause(p->pSat, units + j, units + j + 1)) return 0;
    }
    return 1;
}

static int ff_certified_start(Bmc_EsPar_t *pars, word *truth, PexaMan_t **current, int *act)
{
    unsigned target = (unsigned)truth[0] & 65535u;
    if (pars->nVars != 4 || !ff_full_support(target)) return 0;
    const char *mode = getenv("FF_MODE");
    int plain = mode && !strcmp(mode, "bounded-plain");
    unsigned work = mode && !strcmp(mode, "bounded-unknown") ? 1 : FF_WORK;
    FfCertificate r = ff_bounded(target, FF_BUDGET, work, !plain);
    int stats = getenv("FF_BOUNDED_STATS") != NULL;
    if (stats) printf("FF_BOUND complete=%d found=%d paid=%d nodes=%u pruned=%u\n",
                      r.complete, r.found, r.found ? r.cost : -1, r.visited, r.pruned);
    if (!r.complete) return 0;
    if (!r.found) {
        *act = FF_BUDGET + 2;
        return 0;
    }
    *act = r.cost;
    if (r.gates < 2 || r.gates + pars->nVars > MAJ_NOBJS) return 0;
    int original_nodes = pars->nNodes;
    pars->nNodes = r.gates;
    PexaMan_t *p = PexaManAlloc(pars, truth);
    if (p != NULL) {
        Comb_t query = {0};
        query.r = r.gates - 1;
        query.act = r.cost;
        if (ExactPowerSynthesisCnfBddRange(pars, p, &query, 0) && ff_pin_circuit(p, &r)
                && replay_solve(p, r.cost) == l_True && PexaManGetAct(p) == r.cost) {
            PexaManFree(*current);
            *current = p;
            if (stats) printf("FF_NATIVE gates=%d activity=%d\n", r.gates, r.cost);
            return 1;
        }
        PexaManFree(p);
    }
    pars->nNodes = original_nodes;
    return 0;
}
