/* Record the candidate's emitted signed clauses without running a SAT search.
 * The connectivity numbering follows the pinned PexaManMarkup. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct {
    int nVars, VarMarks[16][2][16];
    unsigned long long pTruth[1];
    void *pSat;
} PexaMan_t;
static int Abc_Var2Lit(int v,int sign) { return 2*v+sign; }
static int sat_solver_addclause(void *unused,int *first,int *end)
{
    (void)unused;
    for (int *p=first;p!=end;++p) printf(" %d",*p);
    printf("\n");
    return 1;
}
#include "orbit_filter.h"

int main(void)
{
    unsigned target;
    int gates;
    while (scanf("%x %d",&target,&gates)==2) {
        if(gates<1 || gates>12) return 1;
        PexaMan_t q={0};
        q.nVars=4;
        q.pTruth[0]=target;
        int next=1+3*gates;
        for(int g=4;g<4+gates;++g) for(int pin=0;pin<2;++pin)
            for(int j=0;j<g-pin;++j) q.VarMarks[g][pin][j]=next++;
        printf("T %04x %d\n",target,gates);
        if(!orbit_filter(&q)) return 2;
    }
    return 0;
}
