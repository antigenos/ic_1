#include <stdio.h>
#include "gate_clauses.h"

typedef struct { int n, lengths[40], clauses[40][5]; } Formula;

static int save(void *context,int *clause,int size)
{
    Formula *f=context;
    if (size>5 || f->n>=40) return 0;
    f->lengths[f->n]=size;
    for (int i=0;i<size;++i) f->clauses[f->n][i]=clause[i];
    ++f->n;
    return 1;
}

static int satisfied(const Formula *f,unsigned values)
{
    for (int i=0;i<f->n;++i) {
        int sat=0;
        for (int j=0;j<f->lengths[i];++j) {
            int lit=f->clauses[i][j];
            sat |= ((values>>(lit/2))&1u) ^ (lit&1);
        }
        if (!sat) return 0;
    }
    return 1;
}

int main(void)
{
    int types[]={5,6,7,8,9};
    unsigned checked=0;
    for (unsigned target=0;target<2;++target) {
        Formula formula={0};
        if (!ff_define_types(&formula,save,types,0) ||
            !ff_type_row(&formula,save,types,3,4,target)) return 2;
        for (unsigned original=0;original<32;++original) {
            unsigned op=(original&7)*2, pair=original>>3;
            unsigned legal=(op==2 || op==4 || op==6 || op==8 || op==14);
            unsigned expect=legal && (((op>>pair)&1u)==target);
            unsigned count=0;
            for (unsigned fresh=0; fresh<32; ++fresh) {
                count+=satisfied(&formula,original|(fresh<<5));
                ++checked;
            }
            if (count!=expect) return 1;
        }
    }
    printf("{\"assignments\":%u,\"extension_count_mismatches\":0}\n",checked);
    return 0;
}
