"""Tiny full truth vectors, finite count products and independent bitset projections."""
from itertools import product, combinations
from collections import Counter
import json


def main():
    rows = 4
    vectors = range(2, 16, 2)  # Normalized nonconstant truth vectors.
    ops = (2, 4, 6, 8, 14)
    weight = lambda a: 2 * a * (rows - a)
    count = lambda x: min(x.bit_count(), rows - x.bit_count())
    tally = Counter()
    examples = {}
    for op, target in product(ops, range(0, 16, 2)):
        pairs = {(count(x), count(y)) for x, y in product(vectors, repeat=2)
                 if sum(((op >> (((x >> i) & 1) + 2*((y >> i) & 1))) & 1) << i
                        for i in range(rows)) == target}
        for remaining in ((), ((1,),), ((2,),), ((1, 2),), ((1, 2), (1, 2))):
            totals = {sum(map(weight, v)) for v in product(*remaining)}
            bits = 1
            for domain in remaining:
                prior, bits = bits, 0
                for a in domain:
                    bits |= prior << weight(a)
            assert totals == {i for i in range(bits.bit_length()) if bits >> i & 1}
            for charged in range(4):
                # A primary input has folded count 2. Fix its exact truth rows too.
                x_choices = vectors if charged & 1 else (10,)
                y_choices = vectors if charged & 2 else (12,)
                valid = {(count(x), count(y)) for x,y in product(x_choices,y_choices)
                         if sum(((op >> (((x >> i)&1)+2*((y >> i)&1)))&1)<<i
                                for i in range(rows)) == target}
                assert valid <= pairs
                for a,b in sorted(valid):
                    used = (weight(a) if charged&1 else 0)+(weight(b) if charged&2 else 0)
                    for lo, hi in combinations(range(0, 35), 2):
                        # Include singleton windows via hi-1.
                        hi -= 1
                        upper = used+min(totals) <= hi
                        interval = upper and used+max(totals) >= lo
                        packed = any(bits >> c & 1 for c in range(max(0,lo-used), hi-used+1))
                        actual = any(lo <= used+sum(map(weight,v)) <= hi for v in product(*remaining))
                        assert packed == actual and (not actual or interval)
                        label = ("hole" if interval and not actual else "interval_rejection"
                                 if upper and not interval else "hit" if actual else "upper_rejection")
                        tally[label] += 1
                        if remaining and label not in examples:
                            examples[label] = dict(op=op,target=target,charged=charged,pair=[a,b],
                                other_domains=remaining,other_sums=sorted(totals),window=[lo,hi],used=used)
    assert all(tally[k] for k in ("hole","interval_rejection","hit","upper_rejection"))
    print(json.dumps(dict(tests=sum(tally.values()), kinds=tally, examples=examples), indent=2))


if __name__ == "__main__":
    main()
