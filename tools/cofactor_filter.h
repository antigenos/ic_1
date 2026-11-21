/* Lower bound on the internal cone forced by a primary output connection.
 * Values are exact three-input internal activities, excluding the output gate.
 * Both phases have equal cost. tools/check_cofactor_table.py verifies this table. */
static const unsigned char cone_opt_three[128] = {
     0,24,24, 0,24, 0,32,24,24,32, 0,24, 0,24,24, 0,
    24, 0,32,24,32,24,78,78,64,54,54,48,54,48,24,24,
    24,32, 0,24,64,54,54,48,32,78,24,78,54,24,48,24,
     0,24,24, 0,54,48,24,24,54,24,48,24, 0,54,54, 0,
    24,32,64,54, 0,24,54,48,32,78,54,24,24,78,48,24,
     0,24,54,48,24, 0,24,24,54,24, 0,54,48,24,54, 0,
    32,78,54,24,54,24, 0,54,78,32,24,78,24,78,54,32,
    24,78,48,24,48,24,54, 0,24,78,54,32,54,32,64,24
};

static unsigned cone_restrict(unsigned truth, int axis, int phase)
{
    unsigned result = 0;
    for (unsigned j = 0; j < 8; ++j) {
        unsigned lo = (1u << axis) - 1;
        unsigned row = (j & lo) | ((j & ~lo) << 1) | ((unsigned)phase << axis);
        result |= ((truth >> row) & 1u) << j;
    }
    return result;
}

static int cone_opt(unsigned truth)
{
    return cone_opt_three[truth >= 128 ? 255 - truth : truth];
}

static int cone_internal_lower(unsigned truth)
{
    int best = 0;
    for (int axis = 0; axis < 4; ++axis) {
        int sum = cone_opt(cone_restrict(truth, axis, 0)) + cone_opt(cone_restrict(truth, axis, 1));
        if (2 * sum > best) best = 2 * sum;
    }
    return best;
}

static int cone_filter(PexaMan_t *p, int bound)
{
    static const unsigned pins[4] = {0xaaaa, 0xcccc, 0xf0f0, 0xff00};
    const char *mode = getenv("REPLAY_CONE");
    if (p->nVars != 4 || p->nNodes < 2 || (mode && !strcmp(mode, "off"))) return 1;
    unsigned target = (unsigned)p->pTruth[0] & 65535u;
    for (int i = 0; i < 4; ++i) {
        unsigned t0 = cone_restrict(target, i, 0), t1 = cone_restrict(target, i, 1);
        if (t0 == 0 || t0 == 255 || t1 == 0 || t1 == 255) continue;
        unsigned g = target ^ pins[i];
        int external = g == 0 || g == 65535;
        for (int j = 0; j < 4; ++j) external |= g == pins[j] || g == (65535u ^ pins[j]);
        if (external) continue;
        int a = Abc_TtCountOnes(g);
        int lower = 2 * a * (16 - a) + cone_internal_lower(g);
        if (lower <= bound) continue;
        /* In pexact the lower-index operand occupies pin 1. Its forced partner
         * above is internal and therefore has a larger index than any primary. */
        int var = p->VarMarks[p->nObjs - 1][1][i];
        int unit = Abc_Var2Lit(var, 1);
        if (getenv("REPLAY_CONE_TRACE"))
            printf("CONE target=%04x gates=%d bound=%d pi=%d g=%04x lower=%d\n",
                   target, p->nNodes, bound, i, g, lower);
        if (!sat_solver_addclause(p->pSat, &unit, &unit + 1)) return 0;
    }
    return 1;
}
