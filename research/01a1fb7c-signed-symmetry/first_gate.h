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

static void iso_prepare(unsigned target, int signed_mode, IsoFirst gates[30])
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
                for (int j = 0; j < n; ++j)
                    if (gates[j].keep && iso_apply(gates[j].function,row) < gates[j].function)
                        gates[j].keep = 0;
            }
        }
    }
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
    if (previous != (int)target || previous_mode != signed_mode) {
        iso_prepare(target,signed_mode,gates);
        previous = (int)target;
        previous_mode = signed_mode;
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
    return 1;
}
