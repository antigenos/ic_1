"""Check native pexact pin ordering and both output polarities on the proved NPN classes."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from check_symmetry import GATE, HERE, MAPS, MASK, PINS, gate, norm, transform
from family import write_once
from repeat_0189 import pin
from witness import simulate


def test_path(target, record):
    simulate(record["circuit"], 4, target)
    signals = dict(zip("abcd", PINS))
    steps = []
    for name, bits, left, right in sorted(GATE.findall(record["circuit"])):
        a, b = signals[left], signals[right]
        value = norm(gate(int(bits, 2), a, b))
        steps.extend((a, b, value))
        signals[name] = value
    assert value == norm(target)
    return " ".join(map(str, (target, len(steps)//3, *steps)))


def verify_printed_selectors(target, cost, selectors):
    count = len(selectors)//3
    names = list("abcd")
    gates = []
    for i, (high, low, op) in enumerate(zip(selectors[::3], selectors[1::3], selectors[2::3])):
        assert 0 <= low < high < len(names) and op in (2, 4, 6, 8, 14)
        if i == count-1 and target & 1:
            op ^= 15
        label = f"{4+i:02d}"
        # PexaManPrintSolution visits selector 1 (low) first, then selector 0 (high).
        gates.append(f"{label} = 4'b{op:04b}( {names[low]} {names[high]} )")
        names.append(label)
    text = [f"Realization of given 4-input function using {count} two-input gates complementary={target&1}:",
            *gates, f"Switching Activity={cost}"]
    result = simulate("\n".join(text)+"\n", 4, target)
    assert result["activity"] == cost and result["gates"] == count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    pin(args.cpu)
    source = (HERE/"prefix-560.json").read_bytes().replace(b"\r\n", b"\n")
    records = json.loads(source)["verified_circuits"]
    expected = {}
    requests = []
    for key, record in records.items():
        t = int(key, 16)
        expected[t] = {transform(t, rows) for _, rows in MAPS}
        requests.append(test_path(t, record))
    with TemporaryDirectory() as folder:
        binary = Path(folder)/("transfer.exe" if os.name == "nt" else "transfer")
        subprocess.run(["g++", "-O2", "-std=c++17", str(HERE/"transfer_probe.cpp"), "-o", str(binary)], check=True)
        run = subprocess.run([str(binary)], input="\n".join(requests)+"\n",
                             text=True, capture_output=True, check=True)
    visited = set()
    sizes = Counter()
    for line in run.stdout.splitlines():
        original, normalized, *pins = map(int, line.split())
        assert normalized in expected[original] and normalized not in visited and not normalized & 1
        expected[original].remove(normalized)
        visited.add(normalized)
        record = records[f"{original:04x}"]["witness"]
        assert len(pins) == 3*record["gates"]
        for target in (normalized, normalized ^ MASK):
            verify_printed_selectors(target, record["activity"], pins)
        sizes[f"{original:04x}"] += 2
    assert not any(expected.values()) and len(sizes) == len(records)
    summary = dict(classes=len(records), normalized_targets=len(visited), verified_truth_tables=2*len(visited),
                   source_sha256=sha256(source).hexdigest(), pins_sha256=sha256(run.stdout.encode()).hexdigest(),
                   truth_tables_per_class=dict(sizes))
    if args.output:
        write_once(args.output, (json.dumps(summary, indent=2)+"\n").encode())
    print(json.dumps({k:v for k,v in summary.items() if k != "truth_tables_per_class"}))


if __name__ == "__main__":
    main()
