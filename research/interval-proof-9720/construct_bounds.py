"""Turn minimum-cost enumeration states into circuits in the original five-gate library."""
import argparse
from itertools import combinations
import json
from pathlib import Path
from zipfile import ZipFile

from family import HERE, VERIFIED, pin, simulate
from family_bounds import enumerate_bounds


def available_gates(signals):
    for x, y in combinations(signals, 2):
        for value, op in ((x & ~y, 4), (y & ~x, 2), (x ^ y, 6), (x & y, 8), (x | y, 14)):
            yield value, op, x, y


def construct(truth, state, activity):
    target = int(truth, 16)
    phase = target & 1
    normal = target ^ (65535 if phase else 0)
    signals = dict(zip((0xaaaa, 0xcccc, 0xf0f0, 0xff00), "abcd"))
    remaining = set(state)
    lines = []

    def emit(op, x, y):
        label = f"{len(lines)+4:02d}"
        lines.append(f"{label} = 4'b{op:04b}( {signals[x]} {signals[y]} )")
        return label

    while remaining:
        gate = next((g for g in available_gates(signals) if g[0] in remaining), None)
        if gate is None:
            raise ValueError(f"State requires a gate outside the author library for {truth}")
        value, op, x, y = gate
        signals[value] = emit(op, x, y)
        remaining.remove(value)
    output = next((g for g in available_gates(signals) if g[0] == normal), None)
    if output is None:
        raise ValueError(f"No legal free output gate for {truth}")
    _, op, x, y = output
    emit(op ^ (15 if phase else 0), x, y)
    header = f"Realization of given 4-input function using {len(lines)} two-input gates complementary={phase}:"
    circuit = "\n".join([header, *reversed(lines), f"Switching Activity={activity}", ""])
    witness = simulate(circuit, 4, target)
    return dict(witness=witness, circuit=circuit)


def audit(data, reference=None):
    frozen = set()
    with ZipFile(HERE / "final-reproduction.zip") as z:
        for arm in ("author", "support", "both"):
            for line in z.read("evidence/e14-main/" + arm + ".jsonl").splitlines():
                row = json.loads(line)
                if row["status"] == VERIFIED:
                    frozen.add(row["experiment"]["truth"])
    bounds = data["bounds"]
    circuits = data["circuits"]
    old = reference if reference is not None else json.loads((HERE / "evidence/family-bounds-432.json").read_bytes())
    assert len(bounds["lower_bounds"]) == len(old["lower_bounds"]) == 208
    assert set(bounds["lower_bounds"]) == set(old["lower_bounds"])
    cutoff = min(bounds["strict_cap"], old["strict_cap"])
    assert all(min(v, cutoff) == min(old["lower_bounds"][t], cutoff) for t, v in bounds["lower_bounds"].items())
    new_counts = {int(k): n for k, n in bounds["states_by_cost"].items() if int(k) < cutoff}
    old_counts = {int(k): n for k, n in old["states_by_cost"].items() if int(k) < cutoff}
    assert new_counts == old_counts
    assert sum(bounds["states_by_cost"].values()) == bounds["states"]
    assert set(circuits) == {t for t, v in bounds["lower_bounds"].items() if v < bounds["strict_cap"]}
    for truth, proof in circuits.items():
        witness = simulate(proof["circuit"], 4, int(truth, 16))
        assert witness == proof["witness"] and witness["activity"] == bounds["lower_bounds"][truth]
    return dict(states=bounds["states"], functions=len(bounds["lower_bounds"]), certified=len(circuits),
                common_with_frozen=len(frozen.intersection(circuits)), absent_from_frozen=sorted(circuits.keys()-frozen))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("build", "audit"))
    cli.add_argument("artifact", type=Path)
    cli.add_argument("--cap", type=int)
    cli.add_argument("--cpu", type=int)
    cli.add_argument("--reference", type=Path, help="Cross-check overlapping lower bounds and state counts against this earlier artifact")
    args = cli.parse_args()
    reference = None
    if args.reference:
        ref = json.loads(args.reference.read_bytes())
        reference = ref.get("bounds", ref)
    if args.action == "build":
        if args.cap is None or args.cpu is None:
            cli.error("build requires --cap and --cpu")
        if args.artifact.exists():
            raise FileExistsError(args.artifact)
        pin(args.cpu)
        plan = json.loads((HERE / "evidence/family-plan.json").read_bytes())
        states = {}
        bounds = enumerate_bounds([c["truth"] for c in plan["cases"]], args.cap, states)
        circuits = {t: construct(t, s, bounds["lower_bounds"][t]) for t, s in sorted(states.items())}
        data = dict(bounds=bounds, circuits=circuits)
        result = audit(data, reference)
        with args.artifact.open("x", encoding="utf8", newline="\n") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
    else:
        result = audit(json.loads(args.artifact.read_bytes()), reference)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
