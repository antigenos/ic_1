"""Check projected lower bounds against actual shared gate cones on four inputs."""
from collections import Counter
from functools import cache
from itertools import combinations, product
import json
import random

from probe_cofactor_cost import cofactor, exact_three_input_costs

PINS = tuple(sum((r >> i & 1) << r for r in range(16)) for i in range(4))
OPT = exact_three_input_costs()


def weight(rows, ones):
    return 2 * ones * (rows - ones)


@cache
def lower(truth):
    return max(2 * sum(OPT[cofactor(truth, bit, v)] for v in (0, 1)) for bit in range(4))


def evaluate(op, left, right):
    return (left & right, left & ~right, ~left & right, left ^ right, left | right)[op]


def run():
    for a, b in product(range(9), repeat=2):
        assert weight(16, a + b) == 2 * (weight(8, a) + weight(8, b) + (a - b)**2)
    depths = Counter()
    stats = Counter()
    minimum_slack = {}
    signals = set()

    def extend(nodes, costs, description, i, j, op, mode):
        left, left_cone = nodes[i]
        right, right_cone = nodes[j]
        value = evaluate(op, left, right)
        ancestors = left_cone | right_cone
        paid = sum(v for n, v in enumerate(costs) if ancestors >> n & 1)
        for polarity in (0, 65535):
            difference = paid - lower(value ^ polarity)
            if difference < 0:
                raise AssertionError(dict(mode=mode, circuit=description + [(i, j, op)],
                                          polarity=polarity, truth=hex(value), cost=paid,
                                          lower=lower(value ^ polarity)))
        minimum_slack[mode] = min(difference, minimum_slack.get(mode, difference))
        signals.add(value)
        stats[mode + "_gates"] += 1
        stats[mode + "_shared_ancestor"] += int(bool(left_cone & right_cone))
        stats[mode + "_positive_lower"] += int(lower(value) > 0)
        depths[(mode, len(costs) + 1)] += 1
        return ((value, ancestors | 1 << len(costs)), weight(16, value.bit_count()))

    pins = [(pin, 0) for pin in PINS]

    def enumerate_all(nodes, costs, description):
        for i, j in combinations(range(len(nodes)), 2):
            for op in range(5):
                node, cost = extend(nodes, costs, description, i, j, op, "exhaustive")
                if len(costs) < 2:
                    enumerate_all(nodes + [node], costs + [cost], description + [(i, j, op)])

    enumerate_all(pins, [], [])
    seed = 20261121
    rng = random.Random(seed)
    for trial in range(4096):
        nodes, costs, description = list(pins), [], []
        for step in range(12):
            i, j = sorted(rng.sample(range(len(nodes)), 2))
            op = rng.randrange(5)
            node, cost = extend(nodes, costs, description, i, j, op, "random")
            nodes.append(node)
            costs.append(cost)
            description.append((i, j, op))
    return dict(split_identities=81, subset="all distinct fanin pairs; five operations; both output phases",
                stats=stats, random_seed=seed, random_circuits=4096, distinct_normalized_signals=len(signals),
                exhaustive_by_depth=[depths["exhaustive", i] for i in (1, 2, 3)],
                minimum_slack=minimum_slack, counterexamples=0)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
