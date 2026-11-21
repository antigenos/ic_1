"""Evaluate the two-terminal lower bound on the preregistered adverse function."""
from functools import cache
from heapq import heappop, heappush
from itertools import combinations
import json
import re

from probe_cofactor_cost import ROOT, exact_three_input_costs


def normal(x):
    return x ^ (255 if x & 1 else 0)


def outcomes(x, y):
    return (x & y, x & ~y, y & ~x, x ^ y, x | y)


def activity(x, rows):
    a = x.bit_count()
    return 2 * a * (rows - a)


@cache
def free_input_opt(h):
    """Exact three-input cost with one supplied free truth vector and free output."""
    base = {0, 0xaa, 0xcc, 0xf0, normal(h)}
    cost_at = {x: 0 for x in base}
    queue, visited = [(0, ())], {()}
    while queue:
        cost, state = heappop(queue)
        available = base.union(state)
        generated = set()
        for x, y in combinations(available, 2):
            generated.update(outcomes(x, y))
        for x in generated - available:
            cost_at.setdefault(x, cost)
            ext_cost = cost + activity(x, 8)
            if ext_cost <= 78:
                ext = tuple(sorted((*state, x)))
                if ext not in visited:
                    visited.add(ext)
                    heappush(queue, (ext_cost, ext))
        if len(cost_at) == 128:
            break
    assert len(cost_at) == 128, (h, len(cost_at))
    return cost_at


def divisions():
    for i in range(4):
        for j in (None, *range(i)):
            halves = []
            for phase in range(2):
                domain = []
                for v in range(8):
                    r = ((v >> i) << (i + 1)) | (v & ((1 << i) - 1))
                    bit = phase ^ ((r >> j & 1) if j is not None else 0)
                    domain.append(r | (bit << i))
                halves.append(domain)
            assert sorted(halves[0] + halves[1]) == list(range(16))
            yield i, j, halves


def project(tt, rows):
    return sum((tt >> r & 1) << k for k, r in enumerate(rows))


def check():
    base = exact_three_input_costs()
    assert all(free_input_opt(0)[normal(x)] == base[x] for x in range(256))
    target = 0xfe74
    budget = 411
    raw = next(json.loads(s) for s in (ROOT / "evidence/e14-main/support.jsonl").read_text().splitlines()
               if json.loads(s)["experiment"]["truth"] == "018b")
    witness_signals = {int(i): sum(int(v) << k for k, v in enumerate(truth)) for i, truth in
                       re.findall(r"^i=(\d+):([01]{16})", raw["solver_output"], re.M)}
    # In this logged solution the output joins the very first gate and gate 09 by XNOR.
    assert witness_signals[4] ^ witness_signals[9] == target
    pins = [witness_signals[i] for i in range(4)]
    first_signals = sorted({h for x, y in combinations(pins, 2) for h in outcomes(x, y)})
    records = []
    for h in first_signals:
        # Four possible joint (T,H) row values force XOR among the five allowed primitives.
        if len({(target >> r & 1, h >> r & 1) for r in range(16)}) < 4:
            records.append(dict(first=f"{h:04x}", forced_xor=False))
            continue
        g = target ^ h
        if g in pins or g == 0:
            raise RuntimeError("would need a separate primary-cost case")
        l_single, l_shared = {}, {}
        for i, j, halves in divisions():
            key = str(i) if j is None else f"{i}={j}"
            restricted = [(project(h, dom), project(g, dom)) for dom in halves]
            l_single[key] = 2 * sum(base[c] for _, c in restricted)
            l_shared[key] = 2 * sum(free_input_opt(normal(a))[normal(c)] for a, c in restricted)
        w_g, w_h = activity(g, 16), activity(h, 16)
        simple = w_g + max(w_h, max(l_single[str(i)] for i in range(4)))
        simple_all = w_g + max(w_h, max(l_single.values()))
        shared_axis = w_g + w_h + max(l_shared[str(i)] for i in range(4))
        shared_all = w_g + w_h + max(l_shared.values())
        records.append(dict(first=f"{h:04x}", forced_xor=True, forced_partner=f"{g:04x}",
                            simple_axes=simple, simple_all=simple_all, shared_axes=shared_axis,
                            shared_all=shared_all, feasible_witness=(witness_signals[4] == h)))
    known = next(r for r in records if r.get("feasible_witness"))
    assert max(known["simple_all"], known["shared_all"]) <= raw["witness"]["activity"]
    metrics = ("simple_axes", "simple_all", "shared_axes", "shared_all")
    return dict(truth="018b", budget=budget, verified_feasible_witness=raw["witness"],
                first_signals=len(records), forced_xor=sum(r["forced_xor"] for r in records),
                excluded={m: sum(r.get(m, 0) > budget for r in records) for m in metrics},
                free_input_tables=free_input_opt.cache_info().currsize, cases=records)


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
