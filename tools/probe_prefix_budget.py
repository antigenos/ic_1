"""Test conditional lower bounds before either output connection is decided."""
from collections import Counter
from functools import cache
from heapq import heappop, heappush
from itertools import combinations, product
import json
import re

from check_cofactor_cones import PINS, weight
from probe_shared_predecessor import ROOT, activity, divisions, normal, outcomes, project


def residual_fourfold(count, mu):
    s = min(count, 8 - count)
    return min(2*(weight(16, s)-mu), 4*weight(8, s)-mu) if s else 0


@cache
def restricted_optima(extras, mu):
    base = {0, 0xaa, 0xcc, 0xf0, *extras}
    # Fourfold integer scaling accommodates fractional costs in the general formula.
    charges = [residual_fourfold(x.bit_count(), mu) for x in range(256)]
    answer = {x: 0 for x in base}
    visited, queue = {()}, [(0, ())]
    while queue:
        cost, state = heappop(queue)
        available = base.union(state)
        gen = set()
        for a, b in combinations(available, 2):
            gen.update(outcomes(a, b))
        for g in gen - available:
            answer.setdefault(g, cost)
            nc = cost + charges[g]
            # Original three-input bounds (<=78) are feasible upper bounds here.
            if nc <= 4*78:
                ext = tuple(sorted((*state, g)))
                if ext not in visited:
                    visited.add(ext)
                    heappush(queue, (nc, ext))
        if len(answer) == 128:
            break
    assert len(answer) == 128
    return answer


CUTS = list(divisions())


@cache
def projections(g):
    return tuple(normal(project(g, domain)) for _, _, halves in CUTS for domain in halves)


def projected_bound(target, prefix, mu, remaining):
    rows = []
    for t, *signals in zip(projections(target), *(projections(h) for h in prefix)):
        extras = tuple(sorted(set(signals) - {0,0xaa,0xcc,0xf0}))
        rows.append(restricted_optima(extras, mu)[t])
    score = 4*mu*remaining + 2*max(rows[i]+rows[i+1] for i in range(0, len(rows), 2))
    return sum(activity(h, 16) for h in prefix) + score/4


def run():
    mu = 20
    for a, b in product(range(9), repeat=2):
        if a+b not in (0,16):
            assert 4*weight(16, a+b) >= 4*mu + 2*(residual_fourfold(a,mu)+residual_fourfold(b,mu))
    target, budget = 0xfe74, 411
    query = next(json.loads(s) for s in (ROOT / "evidence/e14-main/support.jsonl").read_text().splitlines()
                 if json.loads(s)["experiment"]["truth"] == "018b")
    witness = {int(i): sum(int(v) << k for k,v in enumerate(s)) for i,s in
               re.findall(r"^i=(\d+):([01]{16})", query["solver_output"], re.M)}
    records, examples = [], []
    for k in (1,2):
        counts = Counter()
        patterns = set()
        witness_result = None
        for a,b in combinations(PINS,2):
            for h in outcomes(a,b):
                choices = [(h,)] if k == 1 else [(h,g) for x,y in combinations((*PINS,h),2)
                                                   for g in outcomes(x,y)]
                for prefix in choices:
                    counts["syntactic"] += 1
                    if 0 in prefix:
                        counts["constant_prefix_gate"] += 1
                        continue
                    patterns.add(prefix)
                    remaining = 6-k
                    structural = sum(activity(i,16) for i in prefix) + 30*remaining
                    zero = projected_bound(target,prefix,0,remaining)
                    shifted = projected_bound(target,prefix,mu,remaining)
                    current = max(zero,structural)
                    for name, value in (("structural",structural),("plain",zero),("previous_best",current),
                                        ("shifted",shifted),("combined",max(current,shifted))):
                        counts[name + "_over_budget"] += value > budget
                    counts["shift_strict"] += shifted > current
                    if current <= budget < shifted and len(examples)<12:
                        examples.append(dict(prefix=[f"{v:04x}" for v in prefix], structural=structural,
                                             ordinary=zero, shifted=shifted))
                    if all(v==witness[4+i] for i,v in enumerate(prefix)):
                        witness_result = dict(prefix=[f"{v:04x}" for v in prefix],
                                              structural=structural, ordinary=zero, shifted=shifted)
                        assert max(current,shifted) <= query["witness"]["activity"]
        assert witness_result
        records.append(dict(depth=k, distinct_nonconstant= len(patterns), counts=counts, witness=witness_result))
    return dict(truth="018b", gates=7, budget=budget, shift=mu, admissible_count_pairs=79,
                exact_tables=restricted_optima.cache_info().currsize, result=records, examples=examples)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
