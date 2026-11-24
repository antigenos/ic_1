/* Startup-only filter for the registered four-input experiment. */
static int should_guide(PexaMan_t *p, unsigned target)
{
    static const unsigned high[] = {0xaaaa, 0xcccc, 0xf0f0, 0xff00};
    if (p->nVars != 4) return 0;
    int out = p->nObjs - 1;
    for (int i = 0; i < 4; ++i) {
        int low_count = __builtin_popcount(target & (0xffff ^ high[i]));
        int high_count = __builtin_popcount(target & high[i]);
        if (low_count > 1 && low_count < 7 && high_count > 1 && high_count < 7) continue;
        for (int pin = 0; pin < 2; ++pin)
            if (i < out - pin && sat_solver_get_var_value(p->pSat, p->VarMarks[out][pin][i]) == l_Undef)
                return 1;
    }
    return 0;
}

static void give_advice(PexaMan_t *p)
{
    int advice[3 + 2*MAJ_NOBJS], used = 0, out = p->nObjs - 1;
    for (int i = 0; i < 3; ++i) advice[used++] = 1 + 3*(p->nNodes - 1) + i;
    for (int pin = 0; pin < 2; ++pin)
        for (int j = 0; j < out-pin; ++j) advice[used++] = p->VarMarks[out][pin][j];
    sat_solver_set_var_activity(p->pSat, advice, used);
}
