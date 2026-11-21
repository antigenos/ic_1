"""Validate restriction costs against independent strict-bound proofs and archived circuits."""
import argparse
import itertools
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
from lower_bound import cheaper_circuit
from witness import GATE, simulate


def audit(binary):
    with ZipFile(HERE / "reproduction.zip") as archive:
        records = [json.loads(line) for arm in ("author", "support", "both")
                   for line in archive.read(f"evidence/e14-main/{arm}.jsonl").splitlines()]
    cases = sorted({r["experiment"]["truth"] for r in records})
    output = subprocess.run([str(binary.resolve())], input="\n".join(cases), text=True,
                            capture_output=True, check=True).stdout.splitlines()
    costs = list(map(int, output[0].split()))
    assert len(costs) == 256
    for truth in range(0, 256, 2):
        optimum = costs[truth]
        assert optimum == costs[255 ^ truth]
        assert not cheaper_circuit(3, truth, optimum)[0]
        assert cheaper_circuit(3, truth, optimum + 1)[0]
    bounds = {}
    for line in output[1:]:
        case, *values = line.split()
        bounds[case] = list(map(int, values))
    assert set(bounds) == set(cases)

    # A separate assignment-based construction substitutes literals in the
    # original truth table, without using the C implementation's bit insertion.
    for case in cases:
        target = int(case, 16)
        cut_bounds = []
        for pivot in range(4):
            remaining = [i for i in range(4) if i != pivot]
            for other in [None, *remaining]:
                if other is not None and other >= pivot:
                    continue
                restricted = [0, 0]
                for assignment in itertools.product(range(2), repeat=3):
                    bits = dict(zip(remaining, assignment))
                    packed = sum(value << k for k, value in enumerate(assignment))
                    for side in range(2):
                        bits[pivot] = (bits[other] if other is not None else 0) ^ side
                        row = sum(value << i for i, value in bits.items())
                        restricted[side] |= ((target >> row) & 1) << packed
                cut_bounds.append(2 * sum(costs[t] for t in restricted))
        assert len(cut_bounds) == 10 and max(cut_bounds) == bounds[case][0]

    checked = linked = 0
    for r in records:
        if "witness" not in r:
            continue
        case = r["experiment"]["truth"]
        log = r["solver_output"].replace("\r", "")
        witness = simulate(log, 4, int(case, 16))
        assert witness == r["witness"] and bounds[case][0] <= witness["activity"]
        gate = max(GATE.findall(log), key=lambda g: int(g[0]))
        for node in gate[2:]:
            if node in ("a", "b", "c", "d"):
                assert bounds[case][1 + ord(node) - ord("a")] <= witness["activity"]
                linked += 1
        checked += 1
    fixed = json.loads((HERE / "evidence/fixed-point/audit.json").read_text())
    strict = [i for i, lower in enumerate(bounds["0189"][1:])
              if lower > fixed["upper"] and fixed["records"][i]["observed"]["conflict"] == "0"]
    assert strict == [0, 1, 2, 3]
    return dict(three_input_normalized_optima=128, restriction_partitions_checked=len(cases)*10,
                verified_circuits=checked, realized_primary_links=linked,
                omitted_links_at_frozen_fixpoint=strict,
                example_bounds={k:bounds[k] for k in ("0189", "0019", "0198")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(audit(args.binary), indent=2)
    print(result)
    if args.output:
        args.output.write_text(result + "\n", encoding="utf-8")
