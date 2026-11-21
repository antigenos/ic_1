/* Drop a condition only when no supported first/last tuple can match the rest. */
static int endpoint_short(PexaMan_t *p, const int row_masks[30], int output_var)
{
    unsigned supported[150], covered[150]={0}, packed[150];
    int n=0;
    for (int g=0;g<30;++g) for (int j=0;j<5;++j) {
        IsoFirst *f=&endpoint_first[g];
        unsigned code=f->hi | (f->lo<<2) | ((f->op>>1)<<4) | ((endpoint_ops[j]>>1)<<7);
        packed[g*5+j]=code;
        if (row_masks[g]&(1<<j)) supported[n++]=code;
    }
    if (!n) return 0;
    const unsigned fields[]={3,12,16,32,64,128,256,512};
    for (int t=0;t<150;++t) {
        int g=t/5, j=t%5;
        if (!endpoint_first[g].keep || covered[t] || (row_masks[g]&(1<<j))) continue;
        unsigned mask=1023,seed=packed[t];
        for (int k=0;k<8;++k) {
            unsigned trial=mask & ~fields[k];
            int i=0;
            while (i<n && ((seed^supported[i])&trial)) ++i;
            if (i==n) mask=trial;
        }
        int c[8], count=0;
        if (mask&3) c[count++]=Abc_Var2Lit(p->VarMarks[4][0][endpoint_first[g].hi],1);
        if (mask&12) c[count++]=Abc_Var2Lit(p->VarMarks[4][1][endpoint_first[g].lo],1);
        for (int k=0;k<6;++k) if (mask & (16u<<k)) {
            int var=k<3 ? 1+k : output_var+k-3;
            c[count++]=Abc_Var2Lit(var,(seed>>(4+k))&1u);
        }
        if (!sat_solver_addclause(p->pSat,c,c+count)) return 0;
        for (int i=t;i<150;++i) if (!((packed[i]^seed)&mask)) covered[i]=1;
    }
    return 1;
}
