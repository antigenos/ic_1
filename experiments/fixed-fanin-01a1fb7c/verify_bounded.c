#include <stdio.h>
#include "bounded.h"

int main(void)
{
    unsigned truth, work;
    int ceiling, projected;
    while (scanf("%x %d %u %d", &truth, &ceiling, &work, &projected) == 4) {
        if (truth > 65535 || ceiling < 0 || ceiling > FF_MAX_BUDGET || projected < 0 || projected > 2) return 2;
        unsigned norm = truth & 1u ? truth ^ 65535 : truth;
        FfCertificate r = ff_bounded(norm, ceiling, work, projected);
        printf("{\"truth\":\"%04x\",\"cap\":%d,\"projected\":%d,\"work\":%u,"
               "\"complete\":%d,\"found\":%d,\"cost\":%d,\"visited\":%u,\"pruned\":%u,\"chain\":[",
               truth, ceiling, projected, work, r.complete, r.found, r.found ? r.cost : -1,
               r.visited, r.pruned);
        for (int i = 0; i < r.gates; ++i)
            printf("%s[%u,%u,%u]", i ? "," : "", r.chain[i].hi, r.chain[i].lo, r.chain[i].op);
        puts("]}");
    }
    return 0;
}
