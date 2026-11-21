"""Exhaust the free truth vector in the published early-connection example."""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / ".local/reference"
TARGET = 0xFE76
PRIMARY = 0xF0F0
MASK = 0xFFFF
OPS = (2, 4, 6, 8, 14)


def enumerate_vectors(counts, budget):
    before, after = [0, 0], [0, 0]
    examples = []
    for x in range(2, 1 << 16, 2):
        count = min(x.bit_count(), 16 - x.bit_count())
        if count not in counts:
            continue
        values = (x & ~PRIMARY, PRIMARY & ~x, x ^ PRIMARY, x & PRIMARY, x | PRIMARY)
        for op, value in zip(OPS, values):
            if value != TARGET:
                continue
            before[0] |= 1 << count
            before[1] |= 1 << 8
            if 2 * count * (16 - count) <= budget:
                after[0] |= 1 << count
                after[1] |= 1 << 8
                examples.append(dict(op=op, internal=f"{x:04x}", folded_count=count))
    return before, after, examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = REFERENCE / "src/joint_relation.c"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == "69384c16b93bb2de0293e82cbaf1f152aebca38a77539382fc82ee07d1d5e21c"
    old_dir = Path.cwd()
    dlls = None
    try:
        os.chdir(REFERENCE)
        check = runpy.run_path("tools/check_core.py")["main"]
        # Relative compiler paths also work with MinGW in non-ASCII workspaces.
        check.__globals__["ROOT"] = Path(".")
        os.environ.setdefault("CC", "gcc")
        if os.name == "nt":
            dlls = os.add_dll_directory(str(Path(shutil.which(os.environ["CC"])).parent))
        check()
    finally:
        os.chdir(old_dir)
    pair = C.c_uint * 2
    class Result(C.Structure):
        _fields_ = [("supported", pair), ("without_budget", pair)]
    lib = C.CDLL(str(REFERENCE / "build/libproject9_core.so"))
    if dlls:
        dlls.close()
    signature = [C.c_uint] * 3 + [C.POINTER(C.c_uint)] * 3 + [C.c_int, C.c_uint]
    lib.p9_joint_support.argtypes = signature + [C.POINTER(Result)]
    lib.p9_connection_feasible.argtypes = signature
    cases = []
    for counts, budget, expected in [
        ((4, 8), 128, False), ((4, 6, 8), 128, True),
        ((4, 6, 8), 120, True), ((4, 6, 8), 119, False)
    ]:
        before, after, examples = enumerate_vectors(counts, budget)
        arguments = (16, TARGET, 31, pair(1, MASK ^ PRIMARY), pair(0, PRIMARY),
                     pair(sum(1 << a for a in counts), 1 << 8), budget, 1)
        actual = Result()
        assert lib.p9_joint_support(*arguments, C.byref(actual)) == 0
        assert before == list(actual.without_budget) and after == list(actual.supported)
        assert bool(examples) == expected and lib.p9_connection_feasible(*arguments) == int(expected)
        cases.append(dict(counts=counts, budget=budget, without_budget=before,
                          supported=after, witnesses=examples))
    result = dict(target="fe76", primary="f0f0", rows=16, operators=OPS, cases=cases,
                  public_core_checks=json.loads((REFERENCE / "build/validation.json").read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("All four cases matched the independent truth-vector enumeration.")


if __name__ == "__main__":
    main()
