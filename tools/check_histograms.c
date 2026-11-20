#include "histograms.h"
#include <stdio.h>
#include <string.h>

struct brute {
    int bins, r, lo, hi, weights[8];
    long long next, stop;
};

static bool next_brute(struct brute *b, int *v) {
    for (; b->next < b->stop; ) {
        long long code = b->next++;
        int sum = 0, cost = 0;
        for (int j = 0; j < b->bins; ++j) {
            v[j] = (int)(code % (b->r + 1));
            code /= b->r + 1;
            sum += v[j];
            cost += v[j] * b->weights[j];
        }
        if (sum == b->r && cost >= b->lo && cost <= b->hi)
            return true;
    }
    return false;
}

static bool same_vector(const int *counts, void *context) {
    struct brute *b = context;
    int expected[8];
    return next_brute(b, expected) &&
           memcmp(counts, expected, (size_t)b->bins * sizeof(int)) == 0;
}

int main(void) {
    int cases = 0, scratch[8];
    for (int rows = 4; rows <= 16; rows *= 2) {
        for (int r = 1; r <= (rows == 16 ? 4 : 6); ++r) {
            struct brute b = {.bins = rows / 2, .r = r, .stop = 1};
            for (int j = 0; j < b.bins; ++j) {
                b.weights[j] = 2 * (j + 1) * (rows - j - 1);
                b.stop *= r + 1;
            }
            const int widths[] = {0, 1, 37, 75, 2000};
            for (b.lo = 0; b.lo <= r * b.weights[b.bins - 1] + 1; b.lo += 13) {
                for (int k = 0; k < 5; ++k) {
                    b.hi = b.lo + widths[k];
                    b.next = 0;
                    if (!visit_histograms(b.bins - 1, r, 0, b.lo, b.hi, b.weights,
                                          scratch, same_vector, &b) || next_brute(&b, scratch))
                        return 1;
                    ++cases;
                }
            }
        }
    }
    printf("Ordered histogram sequences matched in %d windows.\n", cases);
    return 0;
}
