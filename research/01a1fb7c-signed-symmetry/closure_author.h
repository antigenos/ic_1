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

extern int study_extended_bound(unsigned target,int limit,int *gates,int (*out)[3]);

static int study_at_known(Bmc_EsPar_t *opts, PexaMan_t **manager, word *truth, int cost,int gates,const int (*path)[3])
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
    if (!ExactPowerSynthesisCnfBddRange(opts,next,&node,0)) return 0;
    if (path) {
        for (int i=0;i<gates;++i) {
            int obj=4+i, hi=path[i][0], lo=path[i][1], op=path[i][2];
            if (lo<0 || hi>=obj || lo>=hi) return 0;
            int units[5]={Abc_Var2Lit(next->VarMarks[obj][0][hi],0),Abc_Var2Lit(next->VarMarks[obj][1][lo],0)};
            for (int b=0;b<3;++b) units[2+b]=Abc_Var2Lit(1+3*i+b,1-((op>>(1+b))&1));
            for (int j=0;j<5;++j)
                if (!sat_solver_addclause(next->pSat,units+j,units+j+1)) return 0;
        }
    } else if (!iso_filter(next)) return 0;
    return replay_solve(next,cost)==1 && PexaManGetAct(next)==cost;
}

static int study_at_optimum(Bmc_EsPar_t *opts, PexaMan_t **manager, word *truth,int cost,int gates)
{
    return study_at_known(opts,manager,truth,cost,gates,NULL);
}
