#include "prefix.h"

static int ff_seed_activity(int inputs, unsigned target)
{
    const char *mode = getenv("FF_MODE");
    if (inputs != 4 || (mode && !strcmp(mode, "seed-zero"))) return 0;
    target &= 65535;
    FfRestrictions cuts;
    ff_init_restrictions(&cuts);
    int depth = 2;
    if (mode && !strcmp(mode, "seed-cofactor")) depth = 0;
    if (mode && !strcmp(mode, "seed-prefix1")) depth = 1;
    int lower = ff_prefix_bound(&cuts, target, depth);
    if (getenv("FF_PREFIX_STATS")) printf("FF_SEED target=%04x depth=%d lower=%d\n", target, depth, lower);
    return lower;
}
