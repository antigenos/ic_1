"""Enumerate exact row/column automorphisms of two fixed-gate synthesis prefixes."""
from itertools import combinations, permutations
import json
from check_orbits import OPS, image, normal, op, pins, representatives

MASK = 65535


def boundary_group(target, columns, unpaid_uses):
    # Images of the four input bits completely determine a permutation of rows.
    balanced = [i for i,t in enumerate(columns) if t.bit_count()==8]
    index = {t:i for i,t in enumerate(columns)}
    for indices in permutations(balanced,4):
        unsigned = tuple(sum((columns[j] >> r & 1) << i for i,j in enumerate(indices)) for r in range(16))
        if len(set(unsigned)) != 16:
            continue
        for phase in range(16):
            row = tuple(k ^ phase for k in unsigned)
            if normal(image(target,row),MASK) != target:
                continue
            vectors = [normal(image(t,row),MASK) for t in columns]
            if set(vectors) != set(columns):
                continue
            mapping = tuple(index[t] for t in vectors)
            if {mapping[i] for i in unpaid_uses} == unpaid_uses:
                yield row,mapping


def orbit_min(function, maps):
    return min(normal(image(function,row),MASK) for row,_ in maps)


def check(target):
    target = normal(target,MASK)
    pi = pins(4)
    keep = representatives(4,target)
    counts = dict(prefixes=0,expanded_groups=0,strict_prefixes=0,additional_signal_exclusions=0)
    witness = None
    for i,j in combinations(range(4),2):
        h = pi[i]^pi[j]
        if h not in keep:
            continue
        for l in range(4):
            for c in OPS:
                k = op(c,h,pi[l])
                columns = (*pi,h,k)
                if not k or len(set(columns)) != 6:
                    continue
                unmet = set(range(6)) - {i,j,l,4}
                maps = list(boundary_group(target,columns,unmet))
                old = [m for m in maps if set(m[1][:4]) == set(range(4))]
                candidates = {op(code,a,b) for a,b in combinations(columns,2) for code in OPS}
                candidates.discard(0)
                assert old
                counts["prefixes"] += 1
                counts["expanded_groups"] += len(maps)>len(old)
                diff = sorted(f for f in candidates if orbit_min(f,old)==f and orbit_min(f,maps)<f)
                counts["strict_prefixes"] += bool(diff)
                counts["additional_signal_exclusions"] += len(diff)
                if diff and witness is None:
                    f = diff[0]
                    rep = orbit_min(f,maps)
                    row,col = next(m for m in maps if normal(image(f,m[0]),MASK)==rep)
                    assert rep in candidates
                    witness = dict(first_pins=[i,j],second_primary=l,second_op=c,
                                   columns=list(columns),required=sorted(unmet),row_permutation=row,
                                   column_permutation=col,third=f,representative=rep,
                                   input_group=len(old),boundary_group=len(maps))
    return dict(counts=counts,witness=witness)


if __name__ == "__main__":
    print(json.dumps({t:check(int(t,16)) for t in ("012d","0189")},indent=2))
