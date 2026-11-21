/* Exercise saved_witness.h against complete synthetic feasible-score sets,
 * including improved models, negative statuses and allocation/encoding failures. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MAJ_NOBJS 32
#include "window_proof.h"
typedef struct { int nNodes; } Bmc_EsPar_t;
typedef struct { int act,r; } Comb_t;
typedef struct {
    int nVars,nNodes,lo,hi,score;
    unsigned long long *pTruth;
    Bmc_EsPar_t *pPars;
} PexaMan_t;
enum { l_False=-1,l_True=1,l_Undef=0 };
static int live, faults, calls, fail_at, answers[32][WINDOW_BINS];
static int nvars;
static unsigned next_random(unsigned *seed) { return *seed=*seed*1664525u+1013904223u; }
static PexaMan_t *PexaManAlloc(Bmc_EsPar_t *p,unsigned long long *tt) {
    if (faults==1 && calls==fail_at) return NULL;
    PexaMan_t *q=calloc(1,sizeof(*q));
    assert(q);
    ++live;
    q->nVars=nvars; q->nNodes=p->nNodes; q->pTruth=tt; q->pPars=p;
    return q;
}
static void PexaManFree(PexaMan_t *q) { assert(q && live>0); --live; free(q); }
static int PexaManGetAct(PexaMan_t *q) { return q->score; }
static int ExactPowerSynthesisCnfBddRange(Bmc_EsPar_t *p,PexaMan_t *q,Comb_t *n,int delta) {
    assert(n->r==p->nNodes-1); q->lo=n->act; q->hi=q->lo+delta;
    return !(faults==2 && calls==fail_at);
}
static int replay_solve(PexaMan_t *q,int hi) {
    assert(hi==q->hi);
    if (calls++==fail_at && faults==3) return l_Undef;
    /* Return the dearest admissible model to exercise multiple refinements. */
    for (int s=hi/2; 2*s>=q->lo; --s)
        if (answers[q->nNodes-1][s]) { q->score=2*s; return l_True; }
    return l_False;
}
#include "saved_witness.h"
int main(void) {
    unsigned seed=9720;
    int certified=0, improved=0, fallbacks[4]={0};
    for (int trial=0; trial<800; ++trial) {
        WindowProof ledger;
        nvars=trial%2+3;
        window_init(&ledger,nvars);
        ledger.mode=3;
        memset(answers,0,sizeof(answers));
        int optimum=WINDOW_BINS*2, incumbent=0, initial_r=0;
        /* Raw domain construction was checked separately by check_windows.py. */
        for (int r=nvars-2;r<=7;++r) {
            window_prepare(&ledger,r);
            for(int s=0;s<WINDOW_BINS;++s) if (ledger.table[r][s]==1 && next_random(&seed)%19==0) {
                answers[r][s]=1;
                if (2*s<optimum) optimum=2*s;
                if (2*s>incumbent) { incumbent=2*s; initial_r=r; }
            }
        }
        assert(incumbent>0);
        Bmc_EsPar_t params={initial_r+1};
        unsigned long long truth=nvars==3?0x96:0x6996;
        faults=0;
        PexaMan_t *first=PexaManAlloc(&params,&truth), *result=first;
        first->score=incumbent;
        calls=0; faults=(trial/2)%4; fail_at=trial%7;
        if (window_certify(&ledger,&result)) {
            assert(result->score==optimum && params.nNodes==result->nNodes);
            ++certified; improved+=optimum<incumbent;
        } else {
            assert(faults!=0 && result==first && first->score==incumbent && params.nNodes==initial_r+1);
            ++fallbacks[faults];
        }
        assert(live==1);
        PexaManFree(result);
        assert(live==0);
    }
    assert(improved && fallbacks[1] && fallbacks[2] && fallbacks[3]);
    printf("{\"synthetic_trials\":800,\"certified\":%d,\"improved\":%d,\"fallback_allocation\":%d,"
           "\"fallback_encoding\":%d,\"fallback_unknown\":%d,\"live_after_cleanup\":%d}\n",
           certified,improved,fallbacks[1],fallbacks[2],fallbacks[3],live);
    return 0;
}
