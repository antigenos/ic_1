/* Preserve a representative of every cost-preserving target symmetry orbit. */
static unsigned iso_apply(unsigned truth, const unsigned row[16])
{
    unsigned out = 0;
    for (int i = 0; i < 16; ++i)
        out |= ((truth >> row[i]) & 1u) << i;
    return (out & 1) ? out ^ 65535u : out;
}

typedef struct {
    unsigned function;
    int hi, lo, op, keep;
} IsoFirst;

static int iso_pair_key(const IsoFirst *g)
{
    return g->lo*4 + g->hi;
}

#include "pair_gate.h"

static void iso_prepare(unsigned target, int signed_mode, int pair_first, int pair_mode, IsoFirst gates[30])
{
    static const unsigned pins[4] = {0xaaaa,0xcccc,0xf0f0,0xff00};
    static const int codes[5] = {2,4,6,8,14};
    int n = 0;
    for (int hi = 1; hi < 4; ++hi) for (int lo = 0; lo < hi; ++lo) {
        unsigned a = pins[hi], b = pins[lo];
        unsigned functions[5] = {a & ~b, b & ~a, a ^ b, a & b, a | b};
        for (int j = 0; j < 5; ++j)
            gates[n++] = (IsoFirst){functions[j],hi,lo,codes[j],1};
    }
    if (pair_mode) pair_start(gates);
    for (int a = 0; a < 4; ++a) for (int b = 0; b < 4; ++b) {
        if (a == b) continue;
        for (int c = 0; c < 4; ++c) {
            if (c == a || c == b) continue;
            int d = 6 - a - b - c;
            unsigned permuted[16];
            for (int i = 0; i < 16; ++i)
                permuted[i] = ((i >> a)&1) | (((i >> b)&1)<<1) |
                              (((i >> c)&1)<<2) | (((i >> d)&1)<<3);
            for (unsigned phase = 0; phase < (signed_mode ? 16u : 1u); ++phase) {
                unsigned row[16];
                for (int i = 0; i < 16; ++i) row[i] = permuted[i] ^ phase;
                if (iso_apply(target,row) != target) continue;
                if (pair_mode==2) pair_update(gates,row);
                for (int j = 0; j < n; ++j) {
                    if (!gates[j].keep) continue;
                    unsigned image = iso_apply(gates[j].function,row);
                    unsigned own = gates[j].function;
                    if (pair_first && image != own) {
                        int k = 0;
                        while (k < n && gates[k].function != image) ++k;
                        if (k == n) abort();
                        image += 65536u*iso_pair_key(&gates[k]);
                        own += 65536u*iso_pair_key(&gates[j]);
                    }
                    if (image < own) gates[j].keep = 0;
                }
            }
        }
    }
}

/* The all-step first-occurrence order of ordinary interchangeable inputs. */
static int iso_first_use(PexaMan_t *p, unsigned target)
{
    for (int hi = 1; hi < 4; ++hi) for (int lo = 0; lo < hi; ++lo) {
        unsigned idx = (1u<<hi) | (1u<<lo);
        int equivalent = 1;
        for (unsigned r = 0; r < 16; ++r) {
            unsigned flip = ((r>>hi) ^ (r>>lo)) & 1;
            unsigned swapped = flip ? (r ^ idx) : r;
            if (((target>>r) ^ (target>>swapped)) & 1) { equivalent=0; break; }
        }
        if (!equivalent) continue;
        for (int obj = 4; obj < p->nObjs; ++obj) for (int pin = 0; pin < 2; ++pin) {
            int var = p->VarMarks[obj][pin][hi];
            if (!var) continue;
            int clause[2*MAJ_NOBJS+2], size = 0;
            clause[size++] = Abc_Var2Lit(var,1);
            var = p->VarMarks[obj][1-pin][lo];
            if (var) clause[size++] = Abc_Var2Lit(var,0);
            for (int prev = 4; prev < obj; ++prev) for (int side = 0; side < 2; ++side) {
                var = p->VarMarks[prev][side][lo];
                if (var) clause[size++] = Abc_Var2Lit(var,0);
            }
            if (!sat_solver_addclause(p->pSat,clause,clause+size)) return 0;
        }
    }
    return 1;
}

static int iso_filter(PexaMan_t *p)
{
    static IsoFirst gates[30];
    static int previous = -1, previous_mode = -1;
    const char *mode = getenv("REPLAY_FIRST_SYMMETRY");
    if (p->nVars != 4 || p->nNodes < 2 || p->pPars->fOnlyAnd ||
        (mode && !strcmp(mode,"off"))) return 1;
    int signed_mode = !mode || strcmp(mode,"unsigned") != 0;
    unsigned target = (unsigned)p->pTruth[0] & 65535u;
    if (target & 1) target ^= 65535u;
    int pair_mode = mode && !strcmp(mode,"orbit-prefix") ? 2 : (mode && !strcmp(mode,"sorted-prefix"));
    int classical = pair_mode || (mode && (!strcmp(mode,"first-use") || !strcmp(mode,"combined")));
    if (classical && !iso_first_use(p,target)) return 0;
    if (mode && !strcmp(mode,"first-use")) return 1;
    int pair_first = pair_mode || (mode && (!strcmp(mode,"ordered") || !strcmp(mode,"combined")));
    int cache_mode = signed_mode + 2*pair_first + 4*pair_mode;
    if (previous != (int)target || previous_mode != cache_mode) {
        iso_prepare(target,signed_mode,pair_first,pair_mode,gates);
        previous = (int)target;
        previous_mode = cache_mode;
    }
    for (int j = 0; j < 30; ++j) {
        if (gates[j].keep) continue;
        int clause[5] = {Abc_Var2Lit(p->VarMarks[4][0][gates[j].hi],1),
                         Abc_Var2Lit(p->VarMarks[4][1][gates[j].lo],1)};
        for (int b = 0; b < 3; ++b)
            clause[b+2] = Abc_Var2Lit(1+b,(gates[j].op >> (1+b)) & 1);
        if (getenv("REPLAY_FIRST_TRACE"))
            printf("FIRST target=%04x nodes=%d h=%04x lits=%d,%d,%d,%d,%d\n",
                   target,p->nNodes,gates[j].function,clause[0],clause[1],clause[2],clause[3],clause[4]);
        if (!sat_solver_addclause(p->pSat,clause,clause+5)) return 0;
    }
    return !pair_mode || p->nNodes<3 || pair_filter(p,gates);
}
