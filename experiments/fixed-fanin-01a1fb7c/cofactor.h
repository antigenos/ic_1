/* Lower bounds for a four-input target and each possible primary output fanin. */
#include <limits.h>

typedef struct {
    int opt3[256];
    unsigned rows[10][2][8];
} FfRestrictions;

typedef struct {
    int whole;
    int primary[4];
} FfBounds;

static unsigned ff_primary(unsigned rows, int index)
{
    unsigned signal = 0;
    for (unsigned row = 0; row < rows; ++row)
        signal |= ((row >> index) & 1u) << row;
    return signal;
}

static int ff_activity(unsigned signal, int rows)
{
    int ones = __builtin_popcount(signal);
    return 2 * ones * (rows - ones);
}

/* Record every available free output before charging a new internal signal.
   A repeated signal can use its existing wire for every subsequent fanout. */
static void ff_enumerate3(int best[256], unsigned wires[16], int size, int cost, int limit)
{
    unsigned char generated[256] = {0};
    for (int a = 0; a < size; ++a) generated[wires[a]] = 1;
    for (int i = 0; i < size; ++i) {
        for (int j = 0; j < i; ++j) {
            unsigned a = wires[i], b = wires[j];
            unsigned gates[5] = {a & ~b, b & ~a, a ^ b, a & b, a | b};
            for (int k = 0; k < 5; ++k) {
                unsigned output = gates[k];
                if (cost < best[output]) best[output] = best[255 ^ output] = cost;
                if (generated[output]) continue;
                generated[output] = 1;
                int next = cost + ff_activity(output, 8);
                if (next <= limit) {
                    wires[size] = output;
                    ff_enumerate3(best, wires, size + 1, next, limit);
                }
            }
        }
    }
}

static void ff_init_restrictions(FfRestrictions *cuts)
{
    unsigned wires[16] = {0, 0xaa, 0xcc, 0xf0};
    for (int t = 0; t < 256; ++t) cuts->opt3[t] = INT_MAX;
    ff_enumerate3(cuts->opt3, wires, 4, 0, 78);
    /* The 78 ceiling limits work. Any uncovered function gets the safe bound
       zero. The oracle test checks that this fallback is never needed. */
    for (int t = 0; t < 256; ++t)
        if (cuts->opt3[t] == INT_MAX) cuts->opt3[t] = 0;
    int cut = 0;
    for (int pivot = 0; pivot < 4; ++pivot) {
        unsigned low = (1u << pivot) - 1;
        for (int other = -1; other < pivot; ++other, ++cut) {
            for (unsigned r = 0; r < 8; ++r) {
                unsigned row = (r & low) | ((r & ~low) << 1);
                unsigned same = other < 0 ? 0 : ((row >> other) & 1u);
                cuts->rows[cut][0][r] = row | (same << pivot);
                cuts->rows[cut][1][r] = row | ((1u ^ same) << pivot);
            }
        }
    }
}

static int ff_target_bound(const FfRestrictions *cuts, unsigned truth)
{
    int bound = 0;
    for (int cut = 0; cut < 10; ++cut) {
        int total = 0;
        for (int side = 0; side < 2; ++side) {
            unsigned part = 0;
            for (int row = 0; row < 8; ++row)
                part |= ((truth >> cuts->rows[cut][side][row]) & 1u) << row;
            total += 2 * cuts->opt3[part];
        }
        if (total > bound) bound = total;
    }
    return bound;
}

static void ff_connection_bounds(const FfRestrictions *cuts, unsigned truth, FfBounds *bounds)
{
    bounds->whole = ff_target_bound(cuts, truth);
    for (int i = 0; i < 4; ++i) {
        unsigned h = ff_primary(16, i);
        int best = INT_MAX;
        for (unsigned g = 0; g <= 65535; g += 2) {
            if ((g ^ h) != truth && (g & h) != truth && (g | h) != truth &&
                (g & ~h) != truth && (h & ~g) != truth) continue;
            int lower = ff_activity(g, 16) + ff_target_bound(cuts, g);
            if (lower < best) best = lower;
        }
        bounds->primary[i] = best;
    }
}
