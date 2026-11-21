/* Fixed low operand is a primary. G is the high, charged operand. */
typedef struct {
    unsigned allow_zero[5], allow_one[5];
} FfFixedOperand;

static unsigned ff_ranges[17][17], ff_cost_mask[129];
static int ff_width;

static void ff_width_tables(int rows)
{
    if (rows == ff_width) return;
    ff_width = rows;
    for (int lo = 0; lo <= rows; ++lo) {
        unsigned mask = 0;
        for (int hi = lo; hi <= rows; ++hi) {
            int folded = hi < rows-hi ? hi : rows-hi;
            if (folded) mask |= 1u << folded;
            ff_ranges[lo][hi] = mask;
        }
    }
    for (int cap = 0; cap <= 128; ++cap) {
        ff_cost_mask[cap] = 0;
        for (int a = 1; a <= rows/2; ++a)
            if (2*a*(rows-a) <= cap) ff_cost_mask[cap] |= 1u << a;
    }
}

static FfFixedOperand ff_operand(int rows, unsigned target, unsigned h)
{
    const unsigned codes[5] = {2,4,6,8,14};
    unsigned full = (1u << rows)-1;
    FfFixedOperand p;
    for (int k = 0; k < 5; ++k) {
        unsigned f = codes[k];
        unsigned out0 = (f & 4u) ? h : 0;
        unsigned out1 = ((f & 2u) ? ~h : 0) | ((f & 8u) ? h : 0);
        p.allow_zero[k] = ~(target ^ out0) & full;
        p.allow_one[k] = ~(target ^ out1) & full & ~1u;
    }
    return p;
}

static P9JointResult ff_interval(const FfFixedOperand *p, int rows, unsigned ops,
                                unsigned g_zero, unsigned g_one, unsigned domain, int cap)
{
    unsigned plain = 0, full = (1u << rows)-1;
    for (int k = 0; k < 5; ++k) if (ops & (1u << k)) {
        unsigned zero = p->allow_zero[k] & ~g_one, one = p->allow_one[k] & ~g_zero;
        if ((zero | one) != full) continue;
        int lo = rows - __builtin_popcount(zero), hi = __builtin_popcount(one);
        plain |= ff_ranges[lo][hi] & domain;
        if (plain == domain) break;
    }
    unsigned supported = cap < 0 ? 0 : plain & ff_cost_mask[cap >= 128 ? 128 : cap];
    unsigned pi_count = 1u << (rows/2);
    P9JointResult out = {{supported,supported ? pi_count : 0}, {plain,plain ? pi_count : 0}};
    return out;
}
