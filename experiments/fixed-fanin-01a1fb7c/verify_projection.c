/* Compile standalone. Oracle enumerates actual partner truth tables and gate outputs. */
#include <stdio.h>
#include "projection.h"
#include "xor_condition.h"

static FfProjection oracle[65536];

int main(void)
{
    unsigned long long tests = 0, assignments = 0;
    for (int inputs = 2; inputs <= 4; ++inputs) {
        unsigned n = 1u << inputs, full = (1u << n) - 1;
        for (int i = 0; i < inputs; ++i) {
            unsigned h = 0;
            for (unsigned r = 0; r < n; ++r) h |= ((r >> i) & 1u) << r;
            for (unsigned t = 0; t <= full; t += 2) {
                oracle[t] = (FfProjection){full, full, 0, 0};
            }
            for (unsigned g = 2; g <= full; g += 2) {
                unsigned targets[5] = {g & ~h, h & ~g, g ^ h, g & h, g | h};
                unsigned a = __builtin_popcount(g);
                unsigned bit = 1u << (a <= n/2 ? a : n-a);
                for (int k = 0; k < 5; ++k) {
                    FfProjection *s = &oracle[targets[k]];
                    s->zero &= ~g;
                    s->one &= g;
                    s->counts |= bit;
                    s->operators |= 1u << k;
                    ++assignments;
                }
            }
            for (unsigned t = 0; t <= full; t += 2) {
                FfProjection app = ff_project(n,t,h), ref = oracle[t];
                if (!ref.operators) ref.zero = ref.one = 0;
                if (app.zero != ref.zero || app.one != ref.one ||
                    app.counts != ref.counts || app.operators != ref.operators) {
                    fprintf(stderr,"Mismatch rows=%u input=%d target=%04x\n", n,i,t);
                    return 1;
                }
                if (ff_only_xor(t,inputs) && (ref.operators & ~(1u<<2))) {
                    fprintf(stderr,"Non-XOR counterexample rows=%u input=%d target=%04x\n",n,i,t);
                    return 1;
                }
                ++tests;
            }
        }
    }
    printf("{\"target_primary_cases\":%llu,\"gate_partner_assignments\":%llu,\"mismatches\":0}\n",
           tests, assignments);
    return 0;
}
