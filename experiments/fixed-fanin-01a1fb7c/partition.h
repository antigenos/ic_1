/* Disjoint cases over the original (unmodified) gate function variables. */
static int ff_partition(ReplayQuery *q)
{
    sat_solver *s=q->p->pSat;
    const char *mode=getenv("FF_MODE");
    int audit=getenv("FF_PARTITION_AUDIT")!=NULL;
    int halves=mode && !strcmp(mode,"split-bit");
    int first_bit=1+3*(q->p->nNodes-1);
    const int codes[]={2,4,6,8,14};
    if (audit && !(q->p->nNodes==5 && q->bound==304 && q->target==0xfe76))
        return sat_solver_solve(s,NULL,NULL,0,0,0,0);
    for (int k=0;k<(halves?2:5);++k) {
        int count=halves?1:3;
        lit assumptions[3];
        for (int b=0;b<count;++b) {
            int value=halves?k:(codes[k]>>(b+1))&1;
            assumptions[b]=Abc_Var2Lit(first_bit+b,!value);
        }
        int status=sat_solver_solve(s,assumptions,assumptions+count,0,0,0,0);
        if (audit) {
            printf("FF_SPLIT gates=%d bound=%d code=%d result=%d\n",q->p->nNodes,q->bound,codes[k],status);
        } else if (status==l_True) {
            return status;
        }
        if (status==l_Undef)
            return sat_solver_solve(s,NULL,NULL,0,0,0,0);
    }
    if (audit) {
        int original=sat_solver_solve(s,NULL,NULL,0,0,0,0);
        printf("FF_UNRESTRICTED result=%d\n",original);
        exit(0);
    }
    return l_False;
}
