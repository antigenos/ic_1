/* A forced XOR with an internal first gate supplies that gate as a free
 * divisor when proving the cost of the remaining cone on each half-domain. */
#include "shared_cone_table.h"

static unsigned side_normal(unsigned g)
{
    return (g & 1u ? g ^ 255u : g) >> 1;
}

static unsigned side_restrict(unsigned tt, int axis, int other, int phase)
{
    unsigned mask = (1u << axis) - 1, result = 0;
    for (unsigned v = 0; v < 8; ++v) {
        unsigned row = (v & mask) | ((v & ~mask) << 1);
        unsigned bit = phase ^ (other < 0 ? 0u : (row >> other) & 1u);
        result |= ((tt >> (row | (bit << axis))) & 1u) << v;
    }
    return result;
}

static int side_cost(unsigned g, unsigned h, int diagonals)
{
    int best = 0;
    for (int axis = 0; axis < 4; ++axis)
        for (int j = -1; j < (diagonals ? axis : 0); ++j) {
            int sum = 0;
            for (int phase = 0; phase < 2; ++phase) {
                int k = side_index[side_normal(side_restrict(h, axis, j, phase))];
                if (k < 0) abort();
                sum += side_opt[k][side_normal(side_restrict(g, axis, j, phase))];
            }
            if (2 * sum > best) best = 2 * sum;
        }
    int ag = Abc_TtCountOnes(g), ah = Abc_TtCountOnes(h);
    return 2 * ag * (16 - ag) + 2 * ah * (16 - ah) + best;
}

static int side_filter(PexaMan_t *p, int bound)
{
    static const unsigned pins[] = {0xaaaa, 0xcccc, 0xf0f0, 0xff00};
    static const int codes[] = {2, 4, 6, 8, 14};
    /* Per-process memoization only; every timed CLI invocation pays the setup. */
    static int previous_target = -1, previous_diagonals = -1, lower[4][4][5];
    const char *mode = getenv("REPLAY_SIDE");
    if (p->nVars != 4 || p->nNodes < 3 || (mode && !strcmp(mode, "off"))) return 1;
    int diagonals = !mode || strcmp(mode, "axes");
    unsigned target = (unsigned)p->pTruth[0] & 65535u;
    int prepare = previous_target != (int)target || previous_diagonals != diagonals;
    /* The solver discards a whole query if an added clause contradicts root
     * propagation. Finalize the cache only after visiting every cell. */
    for (int hi = 1; hi < 4; ++hi) for (int lo = 0; lo < hi; ++lo) {
        unsigned a = pins[hi], b = pins[lo];
        unsigned first[5] = {a & ~b, b & ~a, a ^ b, a & b, a | b};
        for (int op = 0; op < 5; ++op) {
            unsigned h = first[op];
            if (prepare) {
                int forced = (target & h) && (target & ~h) &&
                             ((~target) & h) && ((~target) & (~h) & 65535u);
                lower[hi][lo][op] = forced ? side_cost(target ^ h, h, diagonals) : -1;
            }
            if (lower[hi][lo][op] <= bound) continue;
            int clause[6] = {Abc_Var2Lit(p->VarMarks[p->nObjs - 1][1][4], 1),
                             Abc_Var2Lit(p->VarMarks[4][0][hi], 1),
                             Abc_Var2Lit(p->VarMarks[4][1][lo], 1)};
            for (int bit = 0; bit < 3; ++bit)
                clause[bit + 3] = Abc_Var2Lit(1 + bit, (codes[op] >> (bit + 1)) & 1);
            if (getenv("REPLAY_SIDE_TRACE"))
                printf("SIDE target=%04x gates=%d bound=%d pins=%d,%d op=%d first=%04x lower=%d "
                       "lits=%d,%d,%d,%d,%d,%d\n", target, p->nNodes, bound, hi, lo, codes[op], h,
                       lower[hi][lo][op], clause[0], clause[1], clause[2], clause[3], clause[4], clause[5]);
            if (!sat_solver_addclause(p->pSat, clause, clause + 6)) {
                previous_target = -1;
                return 0;
            }
        }
    }
    previous_target = target;
    previous_diagonals = diagonals;
    return 1;
}
