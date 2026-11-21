/* Canonical first-gate functionality under the NPN stabilizer of the target. */
typedef struct {
    unsigned truth;
    int high, low, code, keep;
} OrbitGate;

static unsigned orbit_image(unsigned truth, const unsigned rows[16])
{
    unsigned result = 0;
    for (unsigned r = 0; r < 16; ++r)
        result |= ((truth >> rows[r]) & 1u) << r;
    return result & 1u ? result ^ 65535u : result;
}

static void orbit_prepare(OrbitGate gates[30], unsigned target, int signed_inputs)
{
    const unsigned pin[] = {0xaaaa,0xcccc,0xf0f0,0xff00};
    const int codes[] = {2,4,6,8,14};
    int k = 0;
    for (int h = 1; h < 4; ++h) for (int l = 0; l < h; ++l) {
        unsigned a = pin[h], b = pin[l];
        unsigned signals[] = {a & ~b, b & ~a, a ^ b, a & b, a | b};
        for (int i = 0; i < 5; ++i)
            gates[k++] = (OrbitGate){signals[i],h,l,codes[i],1};
    }
    for (int a = 0; a < 4; ++a) for (int b = 0; b < 4; ++b) {
        if (a == b) continue;
        for (int c = 0; c < 4; ++c) {
            if (c == a || c == b) continue;
            const int d = 6-a-b-c;
            unsigned permuted[16], rows[16];
            for (unsigned r = 0; r < 16; ++r)
                permuted[r] = ((r >> a) & 1) | (((r >> b) & 1) << 1) |
                              (((r >> c) & 1) << 2) | (((r >> d) & 1) << 3);
            for (int phase = 0; phase < (signed_inputs ? 16 : 1); ++phase) {
                for (int r = 0; r < 16; ++r) rows[r] = permuted[r] ^ phase;
                if (orbit_image(target, rows) != target) continue;
                for (int i = 0; i < 30; ++i)
                    if (gates[i].keep && orbit_image(gates[i].truth, rows) < gates[i].truth)
                        gates[i].keep = 0;
            }
        }
    }
}

static int orbit_filter(PexaMan_t *p)
{
    static OrbitGate gates[30];
    static int prior = -1, prior_signed = -1;
    const char *mode = getenv("PEXACT_ORBIT");
    if (p->nVars != 4 || (mode && !strcmp(mode,"off"))) return 1;
    int signed_inputs = !mode || strcmp(mode,"perm") != 0;
    unsigned raw = (unsigned)p->pTruth[0] & 65535u;
    unsigned target = raw & 1u ? raw ^ 65535u : raw;
    if ((int)target != prior || signed_inputs != prior_signed) {
        orbit_prepare(gates,target,signed_inputs);
        prior = target;
        prior_signed = signed_inputs;
        if (getenv("PEXACT_ORBIT_TRACE"))
            for (int i = 0; i < 30; ++i)
                printf("ORBIT target=%04x high=%d low=%d op=%d truth=%04x keep=%d\n",
                       target,gates[i].high,gates[i].low,gates[i].code,gates[i].truth,gates[i].keep);
    }
    for (int first = 0; first < 30; first += 5) {
        int any = 0;
        for (int j = first; j < first+5; ++j) any |= gates[j].keep;
        int clause[5] = {Abc_Var2Lit(p->VarMarks[4][0][gates[first].high],1),
                         Abc_Var2Lit(p->VarMarks[4][1][gates[first].low],1)};
        if (!any) {
            if (!sat_solver_addclause(p->pSat,clause,clause+2)) return 0;
            continue;
        }
        for (int j = first; j < first+5; ++j) {
            if (gates[j].keep) continue;
            for (int bit = 1; bit <= 3; ++bit)
                clause[bit+1] = Abc_Var2Lit(bit,(gates[j].code >> bit) & 1);
            if (!sat_solver_addclause(p->pSat,clause,clause+5)) return 0;
        }
    }
    return 1;
}
