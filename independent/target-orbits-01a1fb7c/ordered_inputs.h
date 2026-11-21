/* Encode first-use ordering of symmetric inputs in pexact's separate pin selectors. */
static int ordered_inputs(PexaMan_t *p)
{
    if (p->nVars!=4) return 1;
    unsigned target=(unsigned)p->pTruth[0] & 65535u;
    for (int earlier=0; earlier<3; ++earlier) for (int later=earlier+1; later<4; ++later) {
        int symmetric=1;
        for (int r=0; r<16 && symmetric; ++r) {
            int flip=((r>>earlier) ^ (r>>later)) & 1;
            int other=r ^ (flip<<earlier) ^ (flip<<later);
            symmetric=((target>>r) & 1u)==((target>>other) & 1u);
        }
        if (!symmetric) continue;
        int clause[2*MAJ_NOBJS+1], length=1;
        for (int g=4; g<p->nObjs; ++g) {
            for (int k=0; k<2; ++k) {
                int v=p->VarMarks[g][k][earlier];
                if (v) clause[length++]=Abc_Var2Lit(v,0);
            }
            for (int k=0; k<2; ++k) {
                int v=p->VarMarks[g][k][later];
                if (!v) continue;
                clause[0]=Abc_Var2Lit(v,1);
                if (!sat_solver_addclause(p->pSat,clause,clause+length)) return 0;
            }
        }
    }
    return 1;
}
