/* Isolate the production filter for differential checking of every emitted literal. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MAJ_NOBJS 45
typedef struct { int fOnlyAnd; } Params;
typedef struct {
    int nVars, nNodes, nObjs, VarMarks[MAJ_NOBJS][2][MAJ_NOBJS];
    unsigned *pTruth;
    Params *pPars;
    void *pSat;
} PexaMan_t;
static int Abc_Var2Lit(int v, int sign) { return 2*v+sign; }
static int sat_solver_addclause(void *unused, int *beg, int *end)
{
    (void)unused;
    fputs("C",stdout);
    while (beg != end) printf(" %d", *beg++);
    putchar('\n');
    return 1;
}
#include "first_gate.h"

int main(void)
{
    unsigned target;
    int gates;
    while (scanf("%x %d",&target,&gates)==2) {
        if (gates<2 || 4+gates>=MAJ_NOBJS) return 1;
        Params settings={0};
        PexaMan_t p={.nVars=4,.nNodes=gates,.nObjs=4+gates,.pPars=&settings,.pTruth=&target};
        int var=1+3*gates;
        for (int i=4; i<p.nObjs; ++i) for (int k=0; k<2; ++k)
            for (int j=0; j<i-k; ++j) p.VarMarks[i][k][j]=var++;
        printf("Q %04x %d\n",target,gates);
        if (!iso_filter(&p)) return 2;
    }
    return 0;
}
