"""Stage-5 diagnostic for the four primary-output connection choices on 0189."""
import ctypes as C
import itertools
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def exact_three_input_costs():
    costs = {}
    records = json.loads((ROOT / "evidence/e14-boundary.json").read_bytes())
    for record in records:
        if len(record["essential_inputs"]) != 3:
            continue
        truth = int(record["reduced"], 16)
        for order in itertools.permutations(range(3)):
            for phase in range(8):
                rows = [phase ^ sum(((r >> p) & 1) << k for k, p in enumerate(order)) for r in range(8)]
                value = sum(((truth >> r) & 1) << k for k, r in enumerate(rows))
                for h in (value, value ^ 255):
                    assert costs.setdefault(h, record["reduced_optimum"]) == record["reduced_optimum"]
    for truth in range(256):
        support = sum(any(((truth >> r) ^ (truth >> (r ^ (1 << b)))) & 1 for r in range(8))
                      for b in range(3))
        if support <= 2:
            costs[truth] = 0
    assert len(costs) == 256
    return costs


def cofactor(truth, bit, value):
    rows = [r for r in range(16) if (r >> bit) & 1 == value]
    return sum(((truth >> r) & 1) << k for k, r in enumerate(rows))


def main():
    costs = exact_three_input_costs()
    target = 0xfe76
    if os.name == "nt":
        runtime = os.add_dll_directory(str(Path(shutil.which("gcc")).parent))
    core = C.CDLL(str(ROOT / ".local/reference/build/libproject9_core.so"))
    pair = C.c_uint * 2
    core.p9_connection_feasible.argtypes = [C.c_uint] * 3 + [C.POINTER(C.c_uint)] * 3 + [C.c_int, C.c_uint]
    items = []
    for i in range(4):
        pin = sum(((r >> i) & 1) << r for r in range(16))
        # Each non-XOR primitive forces a constant target cofactor on at least one pin phase.
        assert all(cofactor(target, i, v) not in (0, 255) for v in (0, 1))
        required = target ^ pin
        a = required.bit_count()
        own = 2 * a * (16 - a)
        # Four gates total. First two charged nodes have minimum costs 96 and 56.
        public = core.p9_connection_feasible(16, target, 31, pair(1, 65535 ^ pin),
                                             pair(0, pin), pair(510, 256), 300 - 152, 1)
        assert public == 1
        splits = []
        for bit in range(4):
            functions = [cofactor(required, bit, v) for v in (0, 1)]
            optima = [costs[v] for v in functions]
            splits.append(dict(bit=bit, cofactors=[f"{v:02x}" for v in functions], optima=optima,
                               cone_lb=2 * sum(optima)))
        bound = own + max(152, max(s["cone_lb"] for s in splits))
        items.append(dict(primary=i, forced_signal=f"{required:04x}", own_cost=own, splits=splits,
                          old_lower=152+own, combined_lower=bound, public_feasible=bool(public),
                          excluded_at_300=bound > 300))
    if os.name == "nt":
        runtime.close()
    print(json.dumps(dict(target="fe76", budget=300, total_gates=4, results=items), indent=2))


if __name__ == "__main__":
    main()
