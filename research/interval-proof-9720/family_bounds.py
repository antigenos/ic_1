"""Independent four-input activity bounds for every registered representative."""
import argparse
from collections import Counter
from itertools import combinations
import json
from pathlib import Path
from struct import Struct
from zipfile import ZipFile

from family import HERE, VERIFIED, pin, simulate


def can_finish(target, signal, available):
    for other in available:
        if (signal ^ other) == target or (signal & other) == target or (signal | other) == target:
            return True
        if (signal & ~other) == target or (other & ~signal) == target:
            return True
    return False


def enumerate_bounds(truths, cap, optimal_states=None, *, terminal=False, deduplicate_terminal=False):
    if not 0 < cap <= 65535:
        raise ValueError("A positive bound in 16-bit range is required")
    normalized = {int(t, 16) ^ (65535 if int(t, 16) & 1 else 0): t for t in truths}
    if terminal and len(normalized) != 1:
        raise ValueError("Terminal output matching requires one target")
    if deduplicate_terminal and not terminal:
        raise ValueError("Terminal deduplication requires direct output matching")
    if len(normalized) != len(truths):
        raise ValueError("Representatives coincide after output normalization")
    primary = (0, 0xaaaa, 0xcccc, 0xf0f0, 0xff00)
    if set(primary).intersection(normalized):
        raise ValueError("Expected full-support representatives")
    weights = [2 * x.bit_count() * (16 - x.bit_count()) for x in range(65536)]
    bounds = {t: cap for t in truths}
    by_cost = Counter()
    # Each state is a sorted set of distinct paid truth vectors. Its cost is their
    # total charge regardless of construction order, so it needs expanding once.
    # Encode little-endian vector tuples without hash collisions from truncation.
    keys = [Struct("<" + "H" * i) for i in range((cap - 1) // 30 + 1)]
    stack = [((), 0)]
    seen = {b""}
    targets = set(normalized)
    if terminal:
        target, name_of_target = next(iter(normalized.items()))
    terminal_edges = 0
    terminal_checks = 0
    terminal_keys = set() if deduplicate_terminal else None
    while stack:
        state, cost = stack.pop()
        by_cost[cost] += 1
        available = primary + state
        outputs = set()
        for x, y in combinations(available, 2):
            outputs.update((x & ~y, y & ~x, x ^ y, x & y, x | y))
        for truth in targets.intersection(outputs):
            name = normalized[truth]
            if cost < bounds[name]:
                bounds[name] = cost
                if optimal_states is not None:
                    optimal_states[name] = state
        outputs.difference_update(available)
        for signal in outputs:
            following_cost = cost + weights[signal]
            if following_cost >= cap:
                continue
            if terminal and following_cost + 30 >= cap:
                terminal_edges += 1
                if following_cost >= bounds[name_of_target]:
                    continue
                if terminal_keys is not None:
                    terminal_state = tuple(sorted((*state, signal)))
                    terminal_key = keys[len(terminal_state)].pack(*terminal_state)
                    if terminal_key in terminal_keys:
                        continue
                    terminal_keys.add(terminal_key)
                terminal_checks += 1
                if can_finish(target, signal, available):
                    bounds[name_of_target] = following_cost
                    if optimal_states is not None:
                        optimal_states[name_of_target] = tuple(sorted((*state, signal)))
                continue
            following = tuple(sorted((*state, signal)))
            key = keys[len(following)].pack(*following)
            if key not in seen:
                seen.add(key)
                stack.append((following, following_cost))
    assert len(seen) == sum(by_cost.values())
    result = dict(inputs=4, strict_cap=cap, states=len(seen), states_by_cost=dict(sorted(by_cost.items())),
                  lower_bounds=dict(sorted(bounds.items())))
    if terminal:
        result["terminal_edges"] = terminal_edges
        result["terminal_checks"] = terminal_checks
        result["retained_terminal_states"] = len(terminal_keys) if terminal_keys is not None else 0
    return result


def compare(bounds, cohort):
    grouped = {}
    runs = 0
    for row in cohort:
        if row["status"] != VERIFIED:
            continue
        truth = row["experiment"]["truth"]
        witness = simulate(row["solver_output"], 4, int(truth, 16))
        assert witness == row["witness"]
        actual = witness["activity"]
        assert grouped.setdefault(truth, actual) == actual
        runs += 1
    certified, gaps = {}, {}
    for truth, actual in sorted(grouped.items()):
        low = bounds["lower_bounds"][truth]
        if low > actual:
            raise ValueError(f"Enumeration excludes the verified witness for {truth}: {low} > {actual}")
        if low == actual:
            certified[truth] = actual
        else:
            gaps[truth] = [low, actual]
    return dict(witnesses=runs, distinct=len(grouped), proved=len(certified),
                certified=certified, remaining_intervals=gaps)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    modes = cli.add_subparsers(dest="action", required=True)
    build = modes.add_parser("build")
    build.add_argument("--cap", type=int, required=True)
    build.add_argument("--cpu", type=int, required=True)
    build.add_argument("--output", type=Path, required=True)
    audit = modes.add_parser("audit")
    audit.add_argument("bounds", type=Path)
    audit.add_argument("--family", type=Path, help="Add the A/C archive to the frozen three-arm witnesses")
    args = cli.parse_args()
    if args.action == "build":
        if args.output.exists():
            raise FileExistsError(args.output)
        pin(args.cpu)
        plan = json.loads((HERE / "evidence/family-plan.json").read_bytes())
        truths = [c["truth"] for c in plan["cases"]]
        assert len(set(truths)) == len(truths) == 208
        result = enumerate_bounds(truths, args.cap)
        with args.output.open("x", encoding="utf8", newline="\n") as f:
            json.dump(result, f, indent=2)
            f.write("\n")
        print(json.dumps(dict(states=result["states"], strict_cap=args.cap, functions=len(truths))))
        return
    bounds = json.loads(args.bounds.read_bytes())
    with ZipFile(HERE / "final-reproduction.zip") as z:
        rows = [json.loads(line) for arm in ("author", "support", "both")
                for line in z.read("evidence/e14-main/" + arm + ".jsonl").splitlines()]
    if args.family:
        with ZipFile(args.family) as z:
            rows.extend(json.loads(line) for arm in "AC" for line in z.read(arm + ".jsonl").splitlines())
    print(json.dumps(compare(bounds, rows), indent=2))


if __name__ == "__main__":
    main()
