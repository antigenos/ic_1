/* Diagnostic entry in the pinned, otherwise original DATE plugin. */
static int ff_read_number(const char **text, int upper)
{
    char *end = NULL;
    long v = strtol(*text, &end, 10);
    if (end == *text || v < 0 || v > upper || (*end && *end != ' ')) return -1;
    *text = end;
    return (int)v;
}

static int ff_native_library(Bmc_EsPar_t *pars, word *truth, PexaMan_t **original, const char *text)
{
    int target = ff_read_number(&text,65535);
    int cost = ff_read_number(&text,10000);
    int count = ff_read_number(&text,MAJ_NOBJS-4);
    if (pars->nVars != 4 || target != (int)(truth[0] & 65535) || cost < 0 || count < 2) return 0;
    int hi[MAJ_NOBJS], lo[MAJ_NOBJS], op[MAJ_NOBJS];
    for (int i=0;i<count;++i) {
        hi[i]=ff_read_number(&text,3+i);
        lo[i]=ff_read_number(&text,3+i);
        int code=ff_read_number(&text,15);
        if (lo[i]<0 || hi[i]<=lo[i] ||
            (code!=2 && code!=4 && code!=6 && code!=8 && code!=14)) return 0;
        /* Printed truth tables use the opposite input-bit order from VarMarks. */
        op[i]=(code & 9) | ((code & 2) << 1) | ((code & 4) >> 1);
    }
    if (*text) return 0;
    pars->nNodes=count;
    PexaMan_t *p=PexaManAlloc(pars,truth);
    if (!p) return 0;
    PexaManFree(*original);
    *original=p;
    Comb_t query={0};
    query.act=cost;
    query.r=count-1;
    if (!ExactPowerSynthesisCnfBddRange(pars,p,&query,0)) return 0;
    for (int i=0;i<count;++i) {
        int high_var=p->VarMarks[4+i][0][hi[i]], low_var=p->VarMarks[4+i][1][lo[i]];
        if (!high_var || !low_var) return 0;
        lit units[5]={Abc_Var2Lit(high_var,0),Abc_Var2Lit(low_var,0)};
        for (int b=0;b<3;++b) units[2+b]=Abc_Var2Lit(1+3*i+b,!((op[i]>>(b+1))&1));
        for (int j=0;j<5;++j) if (!sat_solver_addclause(p->pSat,units+j,units+j+1)) return 0;
    }
    return sat_solver_solve(p->pSat,NULL,NULL,0,0,0,0)==l_True && PexaManGetAct(p)==cost;
}
