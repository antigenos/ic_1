"""Three-variable finite counterexample check for the first-crossing theorem."""
from itertools import combinations, permutations
from functools import cache
from heapq import heappop, heappush
import json

N = 8
MASK = 255
PI = (170, 204, 240)
INF = 10**7


def outcomes(p, q):
    return p & q, p | q, p ^ q, p & ~q, q & ~p


def weight(j):
    return 2*j*(N-j)


@cache
def orbit(p):
    images = set()
    for perm in permutations(range(3)):
        for phase in range(N):
            v = 0
            for x in range(N):
                y = sum(((x >> i) & 1) << j for i, j in enumerate(perm)) ^ phase
                v |= ((p >> y) & 1) << x
            images.add(v ^ (MASK if v & 1 else 0))
    return min(images)


def reference():
    # Independent row-wise gate LUT evaluation. Stop in cost order only after
    # every normalized labeled truth, including nonessential targets, was seen.
    @cache
    def pair(a, b):
        return {sum(((lut >> (2*((a >> i) & 1) + ((b >> i) & 1))) & 1) << i
                    for i in range(N)) for lut in range(0, 16, 2)}
    values = dict.fromkeys((0, *PI), 0)
    queue = [(0, ())]
    seen = {()}
    expanded = 0
    while len(values) < 128:
        cost, state = heappop(queue)
        expanded += 1
        available = PI + state
        options = set().union(*(pair(a, b) for a, b in combinations(available, 2)))
        for t in options:
            values.setdefault(t, cost)
        for x in options.difference((0, *available)):
            child = tuple(sorted((*state, x)))
            if child not in seen:
                seen.add(child)
                heappush(queue, (cost + weight(x.bit_count()), child))
    return values, expanded


def partner(p, t):
    best = INF
    for z, o in zip(outcomes(p, 0), outcomes(p, MASK-1)):
        ones, zeros = z ^ t, o ^ t
        if ones & zeros:
            continue
        low = max(1, ones.bit_count())
        high = (MASK & ~1 & ~zeros).bit_count()
        if low <= high:
            best = min(best, weight(low), weight(high))
    return best


def check(cap, exact):
    states = {()}
    stack = [((), 0)]
    upper = dict.fromkeys((orbit(x) for x in (0, *PI)), 0)
    profile = {}
    boundary = INF
    edges = 0

    def offer(x, cost):
        k = orbit(x)
        upper[k] = min(cost, upper.get(k, INF))

    while stack:
        state, cost = stack.pop()
        avail = PI + state
        new = set().union(*(outcomes(a, b) for a, b in combinations(avail, 2)))
        for t in new:
            offer(t, cost)
        for x in new.difference((0, *avail)):
            nc = cost + weight(x.bit_count())
            if nc <= cap:
                nxt = tuple(sorted((*state, x)))
                if nxt not in states:
                    states.add(nxt)
                    stack.append((nxt, nc))
                continue
            boundary = min(boundary, nc)
            edges += 1
            for p in (*avail, x):
                i = orbit(p)
                profile[i] = min(nc, profile.get(i, INF))
            for a in avail:
                for t in outcomes(a, x):
                    offer(t, nc)

    classes = sorted(set(map(orbit, exact)))
    extra = []
    uniform_count = projected_count = strict = 0
    for t in classes:
        a = min(t.bit_count(), N-t.bit_count())
        double = weight(1) + weight(max(1, a-1))
        single = min(profile.get(orbit(p), INF) + partner(p, t) for p in range(2, MASK, 2))
        unseen = min(boundary + double, single)
        u = upper.get(t, INF)
        uniform = min(u, boundary + weight(1))
        projected = min(u, unseen)
        assert uniform <= projected <= exact[t] <= u, (cap, t, uniform, projected, exact[t], u)
        uniform_count += u == uniform
        projected_count += u == projected
        strict += projected > uniform
        if u == projected and u > uniform:
            extra.append(dict(truth=f'{t:02x}', optimum=u, uniform_lower=uniform))
    return dict(cap=cap, labeled_states=len(states), crossing_edges=edges,
                classes=len(classes), uniform_certified=uniform_count,
                projected_certified=projected_count, strict_bounds=strict, extra=extra)


if __name__ == '__main__':
    direct, count = reference()
    for p in range(0, MASK, 2):
        tab = {}
        for q in range(2, MASK, 2):
            for t in outcomes(p, q):
                tab[t] = min(tab.get(t, INF), weight(q.bit_count()))
        for t in range(0, MASK, 2):
            assert partner(p, t) == tab.get(t, INF), (p, t)
    assert all(direct[t] == direct[orbit(t)] for t in direct)
    print(json.dumps(dict(reference_expanded=count, raw_targets=len(direct),
                          cofactor_checks=128**2,
                          runs=[check(cap, direct) for cap in (0, 24, 32, 48, 56, 64, 72, 80)]),
                     indent=2))
