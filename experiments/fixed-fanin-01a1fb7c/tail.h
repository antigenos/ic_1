/* Min price of a new output operand compatible with one chosen existing wire. */
#include "projection.h"

typedef struct {
    int price[17][17], pair;
    unsigned target, full;
} FfTail;

static unsigned ff_subset(unsigned mask, int count)
{
    unsigned subset = 0;
    for (int i = 0; i < count; ++i) {
        unsigned first = mask & -mask;
        subset |= first;
        mask ^= first;
    }
    return subset;
}

static void ff_init_tail(FfTail *t, unsigned rows, unsigned target)
{
    t->target = target;
    t->full = (1u << rows) - 1u;
    t->pair = INT_MAX;
    unsigned zeros = t->full & ~target & ~1u;
    for (int a = 0; a <= __builtin_popcount(target); ++a) {
        for (int b = 0; b <= __builtin_popcount(zeros); ++b) {
            unsigned h = ff_subset(target, a) | ff_subset(zeros, b);
            FfProjection allowed = ff_project(rows, target, h);
            int price = 10000;
            for (unsigned k = 1; k <= rows / 2; ++k) {
                if (!(allowed.counts & (1u << k))) continue;
                price = 2 * k * (rows - k);
                break;
            }
            t->price[a][b] = price;
            int p = a + b;
            int both = price + 2 * p * ((int)rows - p);
            if (h && both < t->pair) t->pair = both;
        }
    }
}

static int ff_tail_price(const FfTail *t, unsigned wire)
{
    return t->price[__builtin_popcount(wire & t->target)]
                   [__builtin_popcount(wire & ~t->target & t->full)];
}
