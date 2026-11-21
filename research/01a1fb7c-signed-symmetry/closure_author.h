/* Use only a complete independent lower bound, and always return an author SAT circuit. */
extern int study_four_bound(unsigned target, int *gates);

static int study_essential_four(unsigned t)
{
    for (int j=0;j<4;++j) {
        int diff=0;
        for (int r=0;r<16;++r) diff |= ((t>>r)^(t>>(r^(1<<j))))&1u;
        if (!diff) return 0;
    }
    return 1;
}

static int study_at_optimum(Bmc_EsPar_t *opts, PexaMan_t **manager, word *truth, int cost,int gates)
{
    if (gates<2 || gates+4>=MAJ_NOBJS) return 0;
    opts->nNodes=gates;
    PexaMan_t *next=PexaManAlloc(opts,truth);
    if (!next) return 0;
    PexaManFree(*manager);
    *manager=next;
    Comb_t node;
    node.r=gates-1;
    node.act=cost;
    if (!ExactPowerSynthesisCnfBddRange(opts,next,&node,0) || !iso_filter(next)) return 0;
    return replay_solve(next,cost)==1 && PexaManGetAct(next)==cost;
}
