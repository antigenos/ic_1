/* Sort the chain by (larger predecessor, smaller predecessor).
 * The original pin ordering ensures pin 0 is the larger predecessor. */
static int iso_chain_order(PexaMan_t *p)
{
    for (int obj=4; obj+1<p->nObjs; ++obj) for (int h=1; h<obj; ++h) {
        int left=p->VarMarks[obj][0][h],right=p->VarMarks[obj+1][0][h];
        int lits[MAJ_NOBJS+4];
        int n=0;
        lits[n++]=Abc_Var2Lit(left,1);
        for (int b=h; b<=obj; ++b) lits[n++]=Abc_Var2Lit(p->VarMarks[obj+1][0][b],0);
        if (!sat_solver_addclause(p->pSat,lits,lits+n)) return 0;
        for (int lo=1; lo<h; ++lo) {
            n=0;
            lits[n++]=Abc_Var2Lit(left,1);
            lits[n++]=Abc_Var2Lit(right,1);
            lits[n++]=Abc_Var2Lit(p->VarMarks[obj][1][lo],1);
            for (int b=lo; b<h; ++b) lits[n++]=Abc_Var2Lit(p->VarMarks[obj+1][1][b],0);
            if (!sat_solver_addclause(p->pSat,lits,lits+n)) return 0;
        }
    }
    return 1;
}
