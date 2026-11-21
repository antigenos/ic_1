/* Exercise the production C bounds and SAT literals without solving a query. */
#define main symmetry_harness
#include "emit_clauses.c"
#undef main
#include "restriction_filter.h"

int main(void)
{
    unsigned truth;
    int n, budget;
    while (scanf("%x %d %d",&truth,&n,&budget)==3) {
        if (n<2 || n+4>=MAJ_NOBJS) return 1;
        restriction_prepare(truth);
        if (budget<0) {
            printf("T %04x",truth);
            for (int k=0;k<5;k++) printf(" %d",restriction_global[k]);
            putchar('\n');
            for (int j=0;j<30;j++) {
                RestrictionGate *g=&restriction_gates[j];
                printf("G %d %d %d",g->hi,g->lo,g->op);
                for (int k=0;k<5;k++) printf(" %d",g->cost[k]);
                putchar('\n');
            }
        } else {
            Params settings={0};
            PexaMan_t p={.nVars=4,.nNodes=n,.nObjs=4+n,.pTruth=&truth,.pPars=&settings};
            int var=1+3*n;
            for (int i=4;i<p.nObjs;i++) for (int k=0;k<2;k++)
                for (int j=0;j<i-k;j++) p.VarMarks[i][k][j]=var++;
            printf("Q %04x %d %d\n",truth,n,budget);
            int pass=restriction_window(&p,budget,0);
            printf("P %d\n",pass);
            if (pass && !restriction_window(&p,budget,1)) return 2;
        }
    }
    return 0;
}
