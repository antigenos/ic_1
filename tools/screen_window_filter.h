static int screen_lower;

static int screen_any_cost(const unsigned long long *bits, int max, int lo, int hi)
{
    if (lo<0) lo=0;
    if (hi>max) hi=max;
    if (lo>hi) return 0;
    for (int i=lo/64;i<=hi/64;++i) {
        unsigned long long v=bits[i];
        if (i==lo/64) v&=~0ull<<(lo%64);
        if (i==hi/64) v&=~0ull>>(63-hi%64);
        if (v) return 1;
    }
    return 0;
}

static void screen_refine(ReplayQuery *q, ReplaySignal *signals, const int obj[2], int opened,
                          unsigned ops, unsigned *z, unsigned *o, unsigned *domains,
                          int cap, unsigned charged, P9JointResult *result)
{
    if (!q->use_budget || !result->supported[0]) return;
    enum { words=2*MAJ_NOBJS+1 };
    unsigned long long sums[words]={1}, next[words];
    int low=0, high=0, n=q->rows;
    for (int g=q->p->nVars;g<q->p->nObjs-1;++g) {
        if (g==obj[0] || g==obj[1]) continue;
        int largest=0;
        if (SCREEN_HOLES) memset(next,0,sizeof(next));
        for (int a=1;a<=n/2;++a) {
            if (!(signals[g].domain&(1u<<a))) continue;
            largest=2*a*(n-a);
            if (SCREEN_HOLES) {
                int shift=largest%64, off=largest/64;
                for (int w=0;w<=high/64;++w) {
                    next[w+off]|=sums[w]<<shift;
                    if (shift) next[w+off+1]|=sums[w]>>(64-shift);
                }
            }
        }
        if (SCREEN_HOLES) memcpy(sums,next,sizeof(next));
        low+=signals[g].min_cost;
        high+=largest;
    }
    unsigned supported[2]={0,0};
    for (int a=1;a<=n/2;++a) {
        if (!(result->supported[0]&(1u<<a))) continue;
        unsigned one[2]={1u<<a,domains[1]};
        P9JointResult fixed;
        if (p9_joint_support(n,q->target,ops,z,o,one,cap,charged,&fixed)) abort();
        for (int b=1;b<=n/2;++b) {
            if (!(fixed.supported[1]&(1u<<b))) continue;
            int taken=((charged&1u)?2*a*(n-a):0)+((charged&2u)?2*b*(n-b):0);
            if (low+taken>q->bound || high+taken<screen_lower) continue;
            if (SCREEN_HOLES && !screen_any_cost(sums,high,screen_lower-taken,q->bound-taken)) continue;
            if (opened>=0) return; /* Only the existence bit is read on this path. */
            supported[0]|=1u<<a;
            supported[1]|=1u<<b;
        }
    }
    memcpy(result->supported,supported,sizeof(supported));
}
