/* Instrument the same endpoint filtering code that the author solver receives. */
#define main unused_symmetry_probe
#include "emit_clauses.c"
#undef main
#include "restriction_filter.h"
#include "endpoint_filter.h"

int main(void)
{
    unsigned t;
    int n,b;
    while (scanf("%x %d %d",&t,&n,&b)==3) {
        if (n<2 || n+4>=MAJ_NOBJS) return 1;
        endpoint_prepare(t);
        if (b<0) {
            printf("T %04x\n",t);
            for (int g=0;g<30;g++) if (endpoint_first[g].keep) {
                printf("G %04x",endpoint_first[g].function);
                for (int k=0;k<5;k++) for (int j=0;j<5;j++) printf(" %d",endpoint_lb[g][k][j]);
                putchar('\n');
            }
        } else {
            Params opts={0};
            PexaMan_t p={.nVars=4,.nNodes=n,.nObjs=4+n,.pTruth=&t,.pPars=&opts};
            int v=1+3*n;
            for (int i=4;i<p.nObjs;i++) for (int pin=0;pin<2;pin++)
                for (int j=0;j<i-pin;j++) p.VarMarks[i][pin][j]=v++;
            printf("Q %04x %d %d\n",t,n,b);
            int pass=endpoint_window(&p,b,0);
            printf("P %d\n",pass);
            if (pass && !endpoint_window(&p,b,1)) return 2;
        }
    }
    return 0;
}
