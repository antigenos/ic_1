/* Four-input lower bound conditional on the actual paid prefix. */
#include "cofactor.h"

typedef struct {
    unsigned char available;
    unsigned char cost[128];
} FfResidualTable;

static FfResidualTable ff_residual_cache[128][128];

static unsigned ff_slice(const FfRestrictions *cuts, unsigned signal, int cut, int side)
{
    unsigned value = 0;
    for (int i = 0; i < 8; ++i)
        value |= ((signal >> cuts->rows[cut][side][i]) & 1u) << i;
    return (value & 1u) ? (255 ^ value) : value;
}

static unsigned ff_extra_wire(unsigned normalized)
{
    return normalized == 0xaa || normalized == 0xcc || normalized == 0xf0 ? 0 : normalized;
}

static int ff_residual(const FfRestrictions *cuts, unsigned target, unsigned a, unsigned b)
{
    a = ff_extra_wire(a);
    b = ff_extra_wire(b);
    if (a == b) b = 0;
    if (a > b) {
        unsigned temp = a;
        a = b;
        b = temp;
    }
    if (!b) return cuts->opt3[target];
    FfResidualTable *table = &ff_residual_cache[a >> 1][b >> 1];
    if (!table->available) {
        int limit = a ? 42 : 78;
        int best[256];
        for (int i = 0; i < 256; ++i) best[i] = limit + 2;
        unsigned wires[16] = {0, 0xaa, 0xcc, 0xf0, b, a};
        ff_enumerate3(best, wires, a ? 6 : 5, 0, limit);
        for (int i = 0; i < 128; ++i) table->cost[i] = best[2 * i];
        table->available = 1;
    }
    return table->cost[target >> 1];
}

typedef struct {
    const FfRestrictions *cuts;
    unsigned target;
    unsigned target_slices[10][2];
    unsigned wires[6];
    int depth_limit;
} FfPrefix;

static int ff_prefix_lower(FfPrefix *ctx, int depth, int paid, int inherited)
{
    int lower = inherited;
    for (int cut = 0; cut < 10; ++cut) {
        int pair = paid;
        for (int side = 0; side < 2; ++side) {
            unsigned a = depth >= 1 ? ff_slice(ctx->cuts, ctx->wires[4], cut, side) : 0;
            unsigned b = depth >= 2 ? ff_slice(ctx->cuts, ctx->wires[5], cut, side) : 0;
            pair += 2 * ff_residual(ctx->cuts, ctx->target_slices[cut][side], a, b);
        }
        if (pair > lower) lower = pair;
    }
    if (depth == ctx->depth_limit) return lower;
    /* With at most five available signals there are at most 50 different
       generated gate outputs, before removing constants and duplicates. */
    unsigned new_signals[50];
    int count = 0;
    int size = 4 + depth;
    for (int i = 0; i < size; ++i) {
        for (int j = 0; j < i; ++j) {
            unsigned a = ctx->wires[i], b = ctx->wires[j];
            unsigned values[5] = {a & ~b, b & ~a, a ^ b, a & b, a | b};
            for (int k = 0; k < 5; ++k) {
                unsigned v = values[k];
                if (v == ctx->target) return paid;
                if (!v) continue;
                int n = 0;
                while (n < size && ctx->wires[n] != v) ++n;
                if (n < size) continue;
                n = 0;
                while (n < count && new_signals[n] != v) ++n;
                if (n == count) new_signals[count++] = v;
            }
        }
    }
    int cheapest = INT_MAX;
    for (int i = 0; i < count; ++i) {
        unsigned v = new_signals[i];
        int cost = paid + ff_activity(v, 16);
        if (cost >= cheapest) continue;
        ctx->wires[size] = v;
        int branch = ff_prefix_lower(ctx, depth + 1, cost, lower);
        if (branch < cheapest) cheapest = branch;
        if (cheapest == lower) break;
    }
    return cheapest;
}

static int ff_prefix_bound(const FfRestrictions *cuts, unsigned target, int depth)
{
    FfPrefix ctx = {0};
    ctx.cuts = cuts;
    ctx.target = target;
    ctx.depth_limit = depth;
    if (!target) return 0;
    for (int i = 0; i < 4; ++i) {
        ctx.wires[i] = ff_primary(16, i);
        if (target == ctx.wires[i]) return 0;
    }
    for (int cut = 0; cut < 10; ++cut)
        for (int side = 0; side < 2; ++side)
            ctx.target_slices[cut][side] = ff_slice(cuts, target, cut, side);
    return ff_prefix_lower(&ctx, 0, 0, 0);
}
