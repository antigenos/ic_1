/* A single output operation must work on both halves of each input partition. */
#include "endpoint_table.h"

static int endpoint_lb[30][5][5];
static IsoFirst endpoint_first[30];
static const int endpoint_ops[5] = {2,4,6,8,14};

static unsigned endpoint_kinds(int op, int phase, int zero_half)
{
    unsigned mask = 0;
    for (int flip=0; flip < (zero_half ? 1 : 4); ++flip) {
        if (((op>>flip)&1)!=phase) continue;
        int code=0;
        for (int a=0; a<4; ++a) code |= ((((op>>(a^flip))&1)^phase)<<a);
        int kind= code==2 || code==4 ? 0 : code==6 ? 1 : code==8 ? 2 : 3;
        mask |= 1u<<kind;
    }
    return mask;
}

static void endpoint_prepare(unsigned t)
{
    static int previous=-1;
    if (t&1u) t^=65535u;
    if ((int)t==previous) return;
    previous=(int)t;
    memset(endpoint_lb,0,sizeof(endpoint_lb));
    iso_colex_keys=1;
    iso_prepare(t,1,1,0,endpoint_first);
    for (unsigned mask=1; mask<16; ++mask) {
        if (__builtin_popcount(mask)>2) continue;
        unsigned bit=1;
        while ((bit<<1)<=mask) bit<<=1;
        unsigned rows[2][8];
        for (unsigned i=0; i<8; ++i) {
            unsigned base=(i&(bit-1)) | ((i&~(bit-1))<<1);
            rows[0][i]=base | (__builtin_parity(base&mask) ? bit : 0);
            rows[1][i]=rows[0][i]^bit;
        }
        int indices[2], kinds[2][5];
        for (int h=0; h<2; ++h) {
            indices[h]=restriction_project(t,rows[h]);
            for (int j=0; j<5; ++j)
                kinds[h][j]=endpoint_kinds(endpoint_ops[j],(t>>rows[h][0])&1u,h==0);
        }
        for (int g=0; g<30; ++g) {
            if (!endpoint_first[g].keep) continue;
            unsigned signal=endpoint_first[g].function;
            unsigned free_table[2];
            for (int h=0;h<2;++h) free_table[h]=restriction_free[restriction_project(signal,rows[h])];
            int ones=__builtin_popcount(signal);
            for (int k=0;k<5;++k) for (int j=0;j<5;++j) {
                int cost=2*ones*(16-ones);
                for (int h=0;h<2;++h) {
                    int best=255;
                    for (int c=0;c<4;++c) if (kinds[h][j] & (1u<<c)) {
                        int v=endpoint_cost[free_table[h]][k][c][indices[h]];
                        if (v<best) best=v;
                    }
                    cost+=2*best;
                }
                if (cost>endpoint_lb[g][k][j]) endpoint_lb[g][k][j]=cost;
            }
        }
    }
}

static void endpoint_code_literals(int *dest, int first_var, int op)
{
    for (int b=0; b<3; ++b) dest[b]=Abc_Var2Lit(first_var+b,(op>>(1+b))&1);
}

#include "endpoint_short.h"

static int endpoint_window(PexaMan_t *p, int budget, int emit)
{
    const char *mode=getenv("REPLAY_ENDPOINT");
    if (!mode || p->nVars!=4 || p->nNodes<2 || p->pPars->fOnlyAnd) return 1;
    int joint=!strcmp(mode,"joint");
    int compact=!strcmp(mode,"short");
    if (!joint && !compact && strcmp(mode,"margins")) return 1;
    const char *symmetry=getenv("REPLAY_FIRST_SYMMETRY");
    if (!symmetry || strcmp(symmetry,"chain-first")) return 1;
    endpoint_prepare((unsigned)p->pTruth[0] & 65535u);
    int k=p->nNodes<6 ? p->nNodes-2 : 4;
    int rows[30]={0}, cols=0;
    for (int i=0;i<30;++i) if (endpoint_first[i].keep) {
        for (int j=0;j<5;++j)
            if (endpoint_lb[i][k][j]<=budget) rows[i]|=1<<j;
        cols|=rows[i];
    }
    if (!emit || !cols) return cols!=0;
    int output_var=1+3*(p->nNodes-1);
    if (compact) return endpoint_short(p,rows,output_var);
    for (int j=0;j<5;++j) if (!(cols & (1<<j))) {
        int c[3];
        endpoint_code_literals(c,output_var,endpoint_ops[j]);
        if (!sat_solver_addclause(p->pSat,c,c+3)) return 0;
    }
    for (int i=0;i<30;++i) {
        IsoFirst *g=&endpoint_first[i];
        if (!g->keep) continue;
        int c[8]={Abc_Var2Lit(p->VarMarks[4][0][g->hi],1),Abc_Var2Lit(p->VarMarks[4][1][g->lo],1)};
        endpoint_code_literals(c+2,1,g->op);
        if (!rows[i]) {
            if (!sat_solver_addclause(p->pSat,c,c+5)) return 0;
        } else if (joint) {
            for (int j=0;j<5;++j) if ((cols & (1<<j)) && !(rows[i] & (1<<j))) {
                /* The solver can reorder literals, so give it a fresh buffer. */
                int pair[8];
                memcpy(pair,c,5*sizeof(int));
                endpoint_code_literals(pair+5,output_var,endpoint_ops[j]);
                if (!sat_solver_addclause(p->pSat,pair,pair+8)) return 0;
            }
        }
    }
    return 1;
}
