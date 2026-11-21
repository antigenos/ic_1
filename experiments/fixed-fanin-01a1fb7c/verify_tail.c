#include <limits.h>
#include <stdio.h>
#include "tail.h"

int main(void)
{
    unsigned checked = 0;
    for (unsigned target = 0; target < 256; target += 2) {
        FfTail table;
        ff_init_tail(&table, 8, target);
        int minimum = INT_MAX;
        for (unsigned h = 0; h < 256; h += 2) {
            int expected = 10000;
            for (unsigned g = 2; g < 256; g += 2) {
                if ((g & h) != target && (g | h) != target && (g ^ h) != target &&
                    (g & ~h) != target && (h & ~g) != target) continue;
                int weight = __builtin_popcount(g);
                int price = 2 * weight * (8 - weight);
                if (price < expected) expected = price;
            }
            if (ff_tail_price(&table, h) != expected) return 1;
            int weight = __builtin_popcount(h);
            int pair = expected + 2 * weight * (8 - weight);
            if (h && pair < minimum) minimum = pair;
            ++checked;
        }
        if (minimum != table.pair) return 1;
    }
    printf("{\"three_input_target_wire_pairs\":%u,\"two_new_operand_minima\":128}\n", checked);
    return 0;
}
