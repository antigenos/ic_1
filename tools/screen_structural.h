/* Applied before the bounded search. Pin 0 is the larger-index input and
 * represents the low truth-table index bit for pexact's three operator variables. */
static int screen_gate_mismatch(PexaMan_t *p, int obj, int hi, int lo, int code, int *lits)
{
    lits[0] = Abc_Var2Lit(p->VarMarks[obj][0][hi],1);
    lits[1] = Abc_Var2Lit(p->VarMarks[obj][1][lo],1);
    for (int b=0;b<3;++b)
        lits[2+b] = Abc_Var2Lit(1+3*(obj-p->nVars)+b,(code>>(1+b))&1);
    return 5;
}

#ifdef SCREEN_SYMMETRY
static unsigned screen_permute(unsigned f, const int map[4])
{
    unsigned result=0;
    for (int row=0;row<16;++row) {
        int source=0;
        for (int k=0;k<4;++k) source |= ((row>>k)&1)<<map[k];
        result |= ((f>>source)&1u)<<row;
    }
    return result;
}

static int screen_structural(PexaMan_t *p, int bound)
{
    static int target_last=-1, omit[4][4][5];
    static const unsigned pins[]={0xaaaa,0xcccc,0xf0f0,0xff00};
    const int codes[]={2,4,6,8,14};
    if (p->nVars!=4 || p->nNodes<2) return 1;
    unsigned target=(unsigned)p->pTruth[0]&65535u;
    if ((int)target!=target_last) {
        memset(omit,0,sizeof(omit));
        for (int a=0;a<4;++a) for (int b=0;b<4;++b) for (int c=0;c<4;++c) {
            if (a==b || a==c || b==c) continue;
            int perm[]={a,b,c,6-a-b-c};
            if (screen_permute(target,perm)!=target) continue;
            for (int hi=1;hi<4;++hi) for (int lo=0;lo<hi;++lo) {
                unsigned x=pins[hi],y=pins[lo],h[]={x&~y,y&~x,x^y,x&y,x|y};
                for (int i=0;i<5;++i) omit[hi][lo][i] |= screen_permute(h[i],perm)<h[i];
            }
        }
        target_last=target;
    }
    for (int hi=1;hi<4;++hi) for (int lo=0;lo<hi;++lo) for (int op=0;op<5;++op) {
        if (!omit[hi][lo][op]) continue;
        int lits[5];
        screen_gate_mismatch(p,4,hi,lo,codes[op],lits);
        if (!sat_solver_addclause(p->pSat,lits,lits+5)) return 0;
    }
    return 1;
}
#else
static int screen_structural(PexaMan_t *p, int bound)
{
    enum { size=sizeof(prefix_patterns)/sizeof(prefix_patterns[0]) };
    static int target_last=-1, lower[size];
    if (p->nVars!=4 || p->nNodes<3) return 1;
    unsigned target=(unsigned)p->pTruth[0]&65535u;
    if ((int)target!=target_last) {
        unsigned parts[20];
        int n=0;
        for (int i=0;i<4;++i) for (int j=-1;j<i;++j) for (int side=0;side<2;++side) {
            unsigned h=0, mask=(1u<<i)-1;
            for (unsigned v=0;v<8;++v) {
                unsigned row=(v&mask)|((v&~mask)<<1);
                unsigned phase=side^(j<0?0u:((row>>j)&1u));
                h|=((target>>(row|(phase<<i)))&1u)<<v;
            }
            parts[n++]=(h&1u?h^255u:h)>>1;
        }
        for (int k=0;k<size;++k) {
            int best=0;
            const unsigned char *id=prefix_patterns[k].id;
            for (int j=0;j<20;j+=2) {
                int value=2*(prefix_opt[SCREEN_SHIFT][id[j]][parts[j]]+
                             prefix_opt[SCREEN_SHIFT][id[j+1]][parts[j+1]]);
                if (value>best) best=value;
            }
            lower[k]=best+prefix_patterns[k].cost;
        }
        target_last=target;
    }
    int remaining=p->nNodes-3;
    for (int k=0;k<size;++k) {
        if (lower[k]+20*SCREEN_SHIFT*remaining<=bound && prefix_patterns[k].cost+30*remaining<=bound)
            continue;
        int lits[10];
        screen_gate_mismatch(p,4,prefix_patterns[k].hi,prefix_patterns[k].lo,prefix_patterns[k].op,lits);
        screen_gate_mismatch(p,5,prefix_patterns[k].hi2,prefix_patterns[k].lo2,prefix_patterns[k].op2,lits+5);
        if (!sat_solver_addclause(p->pSat,lits,lits+10)) return 0;
    }
    return 1;
}
#endif
