/* Matrices indexed by the 30 binary functions of two primary inputs. */
static unsigned char pair_allowed[30][30];

static unsigned pair_rank(const IsoFirst *g)
{
    return 65536u*iso_pair_key(g)+g->function;
}

static void pair_start(const IsoFirst gates[30])
{
    for (int i=0; i<30; ++i) for (int j=0; j<30; ++j)
        pair_allowed[i][j]=pair_rank(&gates[i])<=pair_rank(&gates[j]);
}

static void pair_update(const IsoFirst gates[30],const unsigned rows[16])
{
    unsigned ranking[30],mapped[30];
    for (int i=0; i<30; ++i) {
        ranking[i]=pair_rank(&gates[i]);
        unsigned truth=iso_apply(gates[i].function,rows);
        int j=0;
        while (j<30 && gates[j].function!=truth) ++j;
        if (j==30) abort();
        mapped[i]=pair_rank(&gates[j]);
    }
    for (int i=0; i<30; ++i) for (int j=0; j<30; ++j) {
        unsigned a=mapped[i],b=mapped[j];
        if (a>b) {unsigned tmp=a; a=b; b=tmp;}
        if (a<ranking[i] || (a==ranking[i] && b<ranking[j])) pair_allowed[i][j]=0;
    }
}

static int pair_clause(PexaMan_t *p, const IsoFirst *first, const IsoFirst *second,
                       int first_op, int second_op)
{
    int lits[10], size=0;
    const IsoFirst *gates[2]={first,second};
    const int need_op[2]={first_op,second_op};
    for (int k=0; k<2; ++k) {
        int obj=4+k;
        lits[size++]=Abc_Var2Lit(p->VarMarks[obj][0][gates[k]->hi],1);
        lits[size++]=Abc_Var2Lit(p->VarMarks[obj][1][gates[k]->lo],1);
        if (need_op[k]) for (int bit=0; bit<3; ++bit)
            lits[size++]=Abc_Var2Lit(1+3*k+bit,(gates[k]->op>>(bit+1))&1);
    }
    return sat_solver_addclause(p->pSat,lits,lits+size);
}

static int pair_filter(PexaMan_t *p,const IsoFirst gates[30])
{
    for (int a=0; a<30; a+=5) for (int b=0; b<30; b+=5) {
        /* Equal rows let us omit the first operation from the clause. A whole
         * forbidden row lets us omit the second operation; earlier first-gate
         * units already rule out unreachable first choices. */
        int masks[5]={0}, first=-1, equal=1;
        for (int i=0; i<5; ++i) if (gates[a+i].keep) {
            for (int j=0; j<5; ++j)
                if (!pair_allowed[a+i][b+j]) masks[i]|=1<<j;
            if (first<0) first=i;
            if (masks[i]!=masks[first]) equal=0;
        }
        for (int i=0; i<5; ++i) {
            if (!gates[a+i].keep || (equal && i!=first) || !masks[i]) continue;
            if (masks[i]==31) {
                if (!pair_clause(p,&gates[a+i],&gates[b],!equal,0)) return 0;
            } else for (int j=0; j<5; ++j) if (masks[i] & (1<<j))
                if (!pair_clause(p,&gates[a+i],&gates[b+j],!equal,1)) return 0;
        }
    }
    return 1;
}
