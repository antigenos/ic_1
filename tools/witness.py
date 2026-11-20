"""Exhaustively simulate the circuit printed by the upstream pexact command."""
import re

GATE = re.compile(r"^(\d+) = 4'b([01]{4})\(\s+(\w+)\s+(\w+)\s+\)$", re.MULTILINE)
NORMAL = {2, 4, 6, 8, 14}


def simulate(text, n, target):
    text = text.replace("\r", "")
    header = re.findall(r"Realization of given (\d+)-input function using (\d+) two-input gates complementary=(\d):", text)
    declared = re.findall(r"^Switching Activity=(\d+)$", text, re.MULTILINE)
    if len(header) != 1 or len(declared) != 1:
        raise ValueError("Missing or ambiguous solution record")
    inputs, count, complement = map(int, header[0])
    gates = sorted((int(i), int(op, 2), hi, lo) for i, op, hi, lo in GATE.findall(text))
    if inputs != n or not count or [g[0] for g in gates] != list(range(n, n + count)):
        raise ValueError("Gate count, identifiers or input count disagree")
    if complement != (target & 1):
        raise ValueError("Output normalization mismatch")
    rows = 1 << n
    signals = {chr(97 + k): sum(((r >> k) & 1) << r for r in range(rows)) for k in range(n)}
    used = set()
    score = 0
    for i, op, hi, lo in gates:
        last = i == gates[-1][0]
        if (op ^ (15 if last and complement else 0)) not in NORMAL:
            raise ValueError(f"Disallowed gate {op:x} at {i}")
        if hi == lo or hi not in signals or lo not in signals:
            raise ValueError(f"Invalid predecessors at gate {i}")
        used.update((hi, lo))
        truth = 0
        for r in range(rows):
            index = 2 * ((signals[hi] >> r) & 1) + ((signals[lo] >> r) & 1)
            truth |= ((op >> index) & 1) << r
        signals[f"{i:02d}"] = truth
        if not last:
            a = truth.bit_count()
            score += 2 * a * (rows - a)
    if used != set(signals) - {f"{gates[-1][0]:02d}"}:
        raise ValueError("Unused primary input or internal gate under the author's all-used encoding")
    if truth != target or score != int(declared[0]):
        raise ValueError(f"Computed truth={truth:x}, score={score}; expected {target:x}, {declared[0]}")
    return {"truth": f"{truth:0{rows//4}x}", "activity": score, "gates": count}
