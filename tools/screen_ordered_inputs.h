/* Direct transfer of ordering interchangeable primary inputs by first use.
 * pexact encodes the two operands separately and allows a simultaneous first use. */
static int screen_input_order(PexaMan_t *p)
{
    if (p->nVars!=4) return 1;
    unsigned target=(unsigned)p->pTruth[0]&65535u;
    for (int a=0;a<4;++a) for (int b=a+1;b<4;++b) {
        int symmetric=1;
        for (int r=0;r<16;++r) {
            int diff=((r>>a)^(r>>b))&1;
            int swapped=r^(diff<<a)^(diff<<b);
            if (((target>>r)^(target>>swapped))&1u) { symmetric=0; break; }
        }
        if (!symmetric) continue;
        int lits[1+2*MAJ_NOBJS], used=1;
        for (int gate=4;gate<p->nObjs;++gate) {
            for (int pin=0;pin<2;++pin) {
                int var=p->VarMarks[gate][pin][a];
                if (var) lits[used++]=Abc_Var2Lit(var,0);
            }
            for (int pin=0;pin<2;++pin) {
                int var=p->VarMarks[gate][pin][b];
                if (!var) continue;
                lits[0]=Abc_Var2Lit(var,1);
                if (!sat_solver_addclause(p->pSat,lits,lits+used)) return 0;
            }
        }
    }
    return 1;
}
