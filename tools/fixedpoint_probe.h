/* Diagnostic-only entry, using the pinned author's CNF builder and ABC's native BCP. */
static int replay_fixedpoint(Bmc_EsPar_t *pars)
{
    if (pars->nVars != 4) return 1;
    word truth[16] = {0};
    Abc_TtReadHex(truth, pars->pTtStr);
    if (truth[0] & 1) Abc_TtNot(truth, Abc_TtWordNum(4));
    if ((truth[0] & 0xffff) != 0xfe76) return 1;
    const int out = 5, gate = 4;
    for (int restrict_domain = 0; restrict_domain <= 1; ++restrict_domain) {
        Comb_t query = {0};
        query.r = 1;
        pars->nNodes = 2;
        PexaMan_t *p = PexaManAlloc(pars, truth);
        sat_solver *s = p->pSat;
        const int encoded = ExactPowerSynthesisCnfBddRange(pars, p, &query, 128);
        int ok = encoded && sat_solver_simplify(s);
        const int selected = p->VarMarks[out][0][gate];
        const int candidate = p->VarMarks[out][1][2];
        if (ok) ok = sat_solver_push(s, Abc_Var2Lit(selected, 0));
        for (int i = 0; ok && restrict_domain && i < p->sizeMap; ++i) {
            MapNpR_t m = p->pMap[i];
            if (m.n_p != 4 && m.n_p != 8)
                ok = sat_solver_push(s, Abc_Var2Lit(m.var, 1));
        }
        printf("REPLAY encoded=%d domain_premises=%d consistent=%d", encoded, restrict_domain, ok);
        if (ok) {
            unsigned domain = 0, zeros = 1, ones = 0, operators = 0;
            for (int i = 0; i < p->sizeMap; ++i)
                if (sat_solver_get_var_value(s, p->pMap[i].var) != l_False)
                    domain |= 1u << p->pMap[i].n_p;
            for (int row = 1; row < 16; ++row) {
                int var = p->iVarMintermBase + 3 + (row - 1) * 3 * p->nNodes;
                int value = sat_solver_get_var_value(s, var);
                if (value == l_False) zeros |= 1u << row;
                if (value == l_True) ones |= 1u << row;
            }
            const unsigned codes[5] = {2, 4, 6, 8, 14};
            for (int i = 0; i < 5; ++i) {
                int possible = 1;
                for (int b = 0; b < 3; ++b) {
                    int v = sat_solver_get_var_value(s, 1 + 3 * (out - 4) + b);
                    if (v != l_Undef && ((v == l_True) != ((codes[i] >> (b + 1)) & 1)))
                        possible = 0;
                }
                if (possible) operators |= 1u << i;
            }
            printf(" fixpoint=%d selected=%d candidate=%d domain=%x zeros=%04x ones=%04x ops=%x",
                   s->qhead == s->qtail, sat_solver_get_var_value(s, selected),
                   sat_solver_get_var_value(s, candidate), domain, zeros, ones, operators);
            int with_candidate = sat_solver_push(s, Abc_Var2Lit(candidate, 0));
            printf(" bcp_with_candidate=%d", with_candidate);
        }
        puts("");
        PexaManFree(p);
    }
    return 0;
}
