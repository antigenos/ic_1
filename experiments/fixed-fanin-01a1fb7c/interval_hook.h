#include "interval.h"

static FfFixedOperand ff_inputs[4];
static int ff_verify, ff_stats;
static unsigned long long ff_calls;

static void ff_prepare(ReplayQuery *q)
{
    ff_calls = 0;
    ff_verify = getenv("FF_CROSSCHECK") != NULL;
    ff_stats = getenv("FF_STATS") != NULL;
    if (q->p->nVars < 2 || q->p->nVars > 4) return;
    ff_width_tables(q->rows);
    for (int pi = 0; pi < q->p->nVars; ++pi) {
        unsigned h = 0;
        for (int r = 1; r < q->rows; ++r) h |= ((r>>pi)&1u) << r;
        ff_inputs[pi] = ff_operand(q->rows,q->target,h);
    }
}

static int ff_support(ReplayQuery *q, const int obj[2], unsigned ops, unsigned z[2], unsigned o[2],
                      unsigned d[2], int cap, unsigned charged, P9JointResult *out)
{
    if (charged != 1 || q->p->nVars < 2 || q->p->nVars > 4)
        return p9_joint_support(q->rows,q->target,ops,z,o,d,cap,charged,out);
    *out = ff_interval(&ff_inputs[obj[1]],q->rows,ops,z[0],o[0],d[0],cap);
    if (ff_stats || ff_verify) ++ff_calls;
    if (ff_verify) {
        P9JointResult ref;
        if (p9_joint_support(q->rows,q->target,ops,z,o,d,cap,charged,&ref) ||
            memcmp(&ref,out,sizeof(ref))) abort();
    }
    return 0;
}
