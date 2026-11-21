#include <stdio.h>
#include "cofactor.h"

int main(void)
{
    FfRestrictions cuts;
    ff_init_restrictions(&cuts);
    for (unsigned t = 0; t < 256; ++t)
        printf("%d%c", cuts.opt3[t], t < 255 ? ' ' : '\n');
    unsigned truth;
    while (scanf("%x", &truth) == 1) {
        if (truth > 65535) return 2;
        unsigned normalized = (truth & 1u) ? (65535 ^ truth) : truth;
        FfBounds result;
        ff_connection_bounds(&cuts, normalized, &result);
        printf("%04x %d", truth, result.whole);
        for (int i = 0; i < 4; ++i) printf(" %d", result.primary[i]);
        putchar('\n');
    }
    return 0;
}
