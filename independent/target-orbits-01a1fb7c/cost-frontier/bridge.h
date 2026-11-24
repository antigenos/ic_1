/* Included after the original interval encoder and the TCJAP trail solver. */
extern int frontier_bound(unsigned raw, int cap, int projected,
                          unsigned short *ordered, int capacity, int *length);

static int frontier_verify(PexaMan_t *trial, Bmc_EsPar_t *pars, unsigned short *internal,
                           int count, int activity)
{
    const char *mode = getenv("PEXACT_FRONTIER_VERIFY");
    int range = mode && strcmp(mode, "range") == 0;
    if (range) {
        Comb_t query;
        query.r = count;
        query.act = activity;
        if (!ExactPowerSynthesisCnfBddRange(pars, trial, &query, 0)) return 0;
    } else {
        if (!PexaManAddCnfStart(trial, pars->fOnlyAnd)) return 0;
        for (int row=1; row<16; ++row)
            if (!PexaManAddCnf(trial, row)) return 0;
    }
    for (int gate=0; gate<count; ++gate) {
        for (int row=1; row<16; ++row) {
            int var = trial->iVarMintermBase + 3*(gate+1) + (row-1)*3*trial->nNodes;
            int lit = Abc_Var2Lit(var, !((internal[gate] >> row) & 1));
            if (!sat_solver_addclause(trial->pSat,&lit,&lit+1)) return 0;
        }
    }
    if (!range && !PexaManAddPClausesBdd(trial)) return 0;
    return replay_solve(trial, activity)==1 && PexaManGetAct(trial)==activity
           && PexaManEval(trial)==-1;
}
