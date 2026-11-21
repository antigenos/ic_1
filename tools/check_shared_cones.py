"""Test side-input bounds on independently costed 4-input networks."""
from functools import cache
from itertools import combinations
import json
import random

from check_cofactor_cones import PINS, evaluate, weight
from probe_shared_predecessor import divisions, free_input_opt, normal, project

CUTS = list(divisions())


@cache
def lower(h, g):
    cost = max(2 * sum(free_input_opt(normal(project(h, dom)))[normal(project(g, dom))]
                       for dom in halves) for _, _, halves in CUTS)
    return weight(16, h.bit_count()) + weight(16, g.bit_count()) + cost


def check():
    counts = dict(exhaustive=0, random=0)
    shares = 0
    min_slack = None

    def extend(nodes, costs, i, j, op, mode):
        nonlocal min_slack, shares
        a, ca = nodes[i]
        b, cb = nodes[j]
        g = evaluate(op, a, b)
        wg = weight(16, g.bit_count())
        union = ca | cb
        if costs:
            # First gate is charged even when it is not an ancestor of g.
            paid = wg + sum(w for k, w in enumerate(costs) if (union | 1) >> k & 1)
            lb = lower(nodes[4][0], g)
            assert lb <= paid, (nodes, costs, i, j, op, paid, lb)
            counts[mode] += 1
            shares += int(bool(union & 1))
            min_slack = paid - lb if min_slack is None else min(min_slack, paid - lb)
        return nodes + [(g, union | (1 << len(costs)))], costs + [wg]

    def walk(nodes, costs):
        for i, j in combinations(range(len(nodes)), 2):
            for op in range(5):
                next_nodes, next_costs = extend(nodes, costs, i, j, op, "exhaustive")
                if len(next_costs) < 3:
                    walk(next_nodes, next_costs)

    pins = [(x, 0) for x in PINS]
    walk(pins, [])
    rng = random.Random(20261121)
    for trial in range(4096):
        nodes, costs = pins, []
        for k in range(12):
            i, j = sorted(rng.sample(range(len(nodes)), 2))
            nodes, costs = extend(nodes, costs, i, j, rng.randrange(5), "random")
    return dict(checked=counts, shared_first_gate=shares, random_seed=20261121,
                distinct_pairs=lower.cache_info().currsize, min_slack=min_slack, counterexamples=0)


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
