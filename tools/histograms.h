#ifndef REPLAY_HISTOGRAMS_H
#define REPLAY_HISTOGRAMS_H

#include <stdbool.h>

typedef bool (*HistogramVisitor)(const int *counts, void *context);

/* Weights increase with folded population. The lowest bin changes fastest in
 * the author's mixed-radix loop. Assigning higher bins first retains its order. */
static bool visit_histograms(int bin, int remaining, int score,
                             int lower, int upper, const int *weights,
                             int *counts, HistogramVisitor visit, void *context)
{
    if (score + remaining * weights[0] > upper ||
        score + remaining * weights[bin] < lower)
        return true;
    if (bin == 0) {
        counts[0] = remaining;
        return visit(counts, context);
    }
    for (int n = 0; n <= remaining; ++n) {
        counts[bin] = n;
        if (!visit_histograms(bin - 1, remaining - n, score + n * weights[bin],
                              lower, upper, weights, counts, visit, context))
            return false;
    }
    return true;
}
#endif
