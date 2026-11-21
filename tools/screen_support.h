/* Alternative evaluations of the frozen public relation. Build one per variant. */
#ifdef SCREEN_MEMO
static int screen_support(unsigned n, unsigned t, unsigned ops, const unsigned z[2],
                          const unsigned o[2], const unsigned d[2], int cap,
                          unsigned charged, P9JointResult *result)
{
    typedef struct { unsigned key[11]; P9JointResult value; } Entry;
    static Entry table[1024];
    unsigned key[] = {n,t,ops,z[0],z[1],o[0],o[1],d[0],d[1],(unsigned)cap,charged};
    unsigned hash = 2166136261u;
    for (int i = 0; i < 11; ++i) hash = (hash ^ key[i]) * 16777619u;
    Entry *e = &table[(hash ^ (hash >> 16)) & 1023];
    if (!memcmp(key,e->key,sizeof(key))) {
        *result = e->value;
        return 0;
    }
    int status = p9_joint_support(n,t,ops,z,o,d,cap,charged,result);
    if (!status) {
        memcpy(e->key,key,sizeof(key));
        e->value = *result;
    }
    return status;
}
#else
static int screen_support(unsigned n, unsigned t, unsigned ops, const unsigned z[2],
                          const unsigned o[2], const unsigned d[2], int cap,
                          unsigned charged, P9JointResult *result)
{
    if (charged == 1 || charged == 2) {
        int internal = charged == 2, primary = 1 - internal;
        unsigned mask = (1u << n) - 1u, pin = o[primary];
        if ((z[primary] | pin) == mask && (t & pin) && (t & ~pin) &&
            (~t & pin) && (~t & ~pin & mask)) {
            memset(result, 0, sizeof(*result));
            unsigned g = t ^ pin;
            int a = __builtin_popcount(g), b = __builtin_popcount(pin);
            unsigned di = 1u << (a < n-a ? a : n-a), dp = 1u << (b < n-b ? b : n-b);
            if ((ops & 4u) && !(g & z[internal]) && !(~g & o[internal]) &&
                (d[internal] & di) && (d[primary] & dp)) {
                result->without_budget[primary] = dp;
                result->without_budget[internal] = di;
                if ((int)(2*a*(n-a)) <= cap) {
                    result->supported[primary] = dp;
                    result->supported[internal] = di;
                }
            }
            return 0;
        }
    }
    return p9_joint_support(n,t,ops,z,o,d,cap,charged,result);
}
#endif
