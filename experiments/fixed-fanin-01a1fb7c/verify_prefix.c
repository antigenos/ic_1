#include <stdio.h>
#include <string.h>
#include "prefix.h"

int main(int argc, char **argv)
{
    FfRestrictions cuts;
    ff_init_restrictions(&cuts);
    unsigned truth;
    if (argc == 2 && !strcmp(argv[1], "residual")) {
        unsigned a, b;
        while (scanf("%x %x %x", &truth, &a, &b) == 3) {
            if (truth > 254 || a > 254 || b > 254 || ((truth | a | b) & 1)) return 2;
            printf("%d\n", ff_residual(&cuts, truth, a, b));
        }
        return 0;
    }
    while (scanf("%x", &truth) == 1) {
        if (truth > 65535) return 2;
        unsigned target = (truth & 1u) ? truth ^ 65535 : truth;
        printf("%04x", truth);
        for (int depth = 0; depth <= 2; ++depth)
            printf(" %d", ff_prefix_bound(&cuts, target, depth));
        putchar('\n');
    }
    return 0;
}
