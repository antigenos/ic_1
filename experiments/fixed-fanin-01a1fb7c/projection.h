/* Exact projection for a normalized nonconstant partner G and a known H. */
typedef struct {
    unsigned zero, one, counts, operators;
} FfProjection;

static FfProjection ff_project(unsigned n, unsigned target, unsigned h)
{
    const unsigned codes[5] = {2, 4, 6, 8, 14};
    unsigned full = (1u << n) - 1u;
    FfProjection result = {full, full, 0, 0};
    for (int k = 0; k < 5; ++k) {
        unsigned f = codes[k];
        unsigned y0 = (f & 4u) ? h : 0;
        unsigned y1 = ((f & 2u) ? ~h : 0) | ((f & 8u) ? h : 0);
        unsigned allow0 = ~(y0 ^ target) & full;
        unsigned allow1 = ~(y1 ^ target) & full & ~1u;
        if ((allow0 | allow1) != full || !allow1) continue;
        unsigned must1 = full ^ allow0;
        if (!must1 && !(allow1 & (allow1 - 1))) must1 = allow1;
        int lo = __builtin_popcount(must1), hi = __builtin_popcount(allow1);
        for (int a = lo > 0 ? lo : 1; a <= hi; ++a) {
            unsigned folded = (unsigned)a <= n/2 ? (unsigned)a : n - (unsigned)a;
            result.counts |= 1u << folded;
        }
        result.zero &= full ^ allow1;
        result.one &= must1;
        result.operators |= 1u << k;
    }
    if (!result.operators) result.zero = result.one = 0;
    return result;
}
