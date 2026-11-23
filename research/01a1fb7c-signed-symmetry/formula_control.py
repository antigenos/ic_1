"""Exact fanout-free control under the DATE charged-internals/free-output model."""
import argparse
from collections import Counter
import json
from pathlib import Path
from time import perf_counter

from check_symmetry import GATE, HERE, PINS, norm, weight
from family import write_once
from repeat_0189 import pin
from witness import simulate


def formulas(limit):
    # A child formula is paid for in full on each use. The final gate costs zero.
    paid_buckets = [[] for _ in range(limit+1)]
    paid_buckets[0] = [0, *PINS]
    output_cost = dict.fromkeys(paid_buckets[0], 0)
    parent = {}
    pairs = 0
    for budget in range(0, limit+1, 2):
        for left_cost in range(0, budget//2+1, 2):
            right_cost = budget-left_cost
            for a in paid_buckets[left_cost]:
                for b in paid_buckets[right_cost]:
                    if a == b or (left_cost == right_cost and a > b):
                        continue
                    pairs += 1
                    for signal, op in ((a & ~b,4), (b & ~a,2), (a ^ b,6), (a & b,8), (a | b,14)):
                        if signal in output_cost:
                            continue
                        output_cost[signal] = budget
                        parent[signal] = a, b, op
                        charged = budget+weight(signal)
                        if charged <= limit:
                            paid_buckets[charged].append(signal)
    return output_cost, parent, pairs


def circuit(target, value, parent):
    gates = []
    names = dict(zip(PINS, "abcd"))
    def emit(signal, final=False):
        if signal in names:
            return names[signal]
        a, b, op = parent[signal]
        left, right = emit(a), emit(b)
        label = f"{4+len(gates):02d}"
        if final and target & 1:
            op ^= 15
        gates.append(f"{label} = 4'b{op:04b}( {left} {right} )")
        return label
    emit(norm(target), True)
    text = [f"Realization of given 4-input function using {len(gates)} two-input gates complementary={target&1}:",
            *gates, f"Switching Activity={value}"]
    return "\n".join(text)+"\n"


def shared(text):
    uses = Counter(v for _, _, a, b in GATE.findall(text) for v in (a,b) if v.isdigit())
    return any(n > 1 for n in uses.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    pin(args.cpu)
    dag = json.loads((HERE/"prefix-560.json").read_bytes())
    start = perf_counter()
    values, parents, pairs = formulas(dag["limit"])
    enum_s = perf_counter()-start
    cases = {}
    for key, exact in dag["certificates"].items():
        target = int(key,16)
        tree = values.get(norm(target))
        case = dict(dag=exact, formula=tree)
        if tree is not None:
            assert exact is not None and exact <= tree
            text = circuit(target, tree, parents)
            case.update(circuit=text, witness=simulate(text, 4, target))
            assert not shared(text)
        if exact is not None:
            old = dag["verified_circuits"][key]["circuit"]
            if not shared(old):
                assert exact == tree
        case["sharing"] = ("unknown_above_bound" if exact is None else
                           "unnecessary" if tree == exact else "required")
        cases[key] = case
    summary = dict(limit=dag["limit"], targets=len(cases), pairs=pairs, free_signals=len(values),
                   finite_formulas=sum(c["formula"] is not None for c in cases.values()),
                   sharing=dict(Counter(c["sharing"] for c in cases.values())))
    result = dict(**summary, enumeration_s=enum_s, cases=cases)
    if args.output:
        write_once(args.output,(json.dumps(result,indent=2)+"\n").encode())
    print(json.dumps(dict(**summary,enumeration_s=enum_s)))


if __name__ == "__main__":
    main()
