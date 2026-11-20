"""Enumerate small straight-line circuits, including dead gates and repeated truth vectors."""
from itertools import combinations
import json


def check(n, levels):
    rows = 1 << n
    primary = tuple(sum(((r >> i) & 1) << r for r in range(rows)) for i in range(n))
    totals = [0] * levels
    counts = [set() for _ in range(levels)]

    def visit(signals, g):
        stride = 1 << max(0, n - g - 2)
        for x, y in combinations(signals, 2):
            for z in (x & y, x & ~y, y & ~x, x | y, x ^ y):
                count = min(z.bit_count(), rows - z.bit_count())
                assert count % stride == 0, (signals, g, z, stride)
                totals[g] += 1
                counts[g].add(count)
                if g + 1 < levels:
                    visit((*signals, z), g + 1)
    visit(primary, 0)
    return dict(inputs=n, gates_checked=totals, observed_folded_counts=list(map(sorted, counts)))


if __name__ == "__main__":
    print(json.dumps([check(n, 3) for n in (2, 3, 4)], indent=2))
