"""Recover and verify the pinned ABC four-input NPN representative family."""
from itertools import permutations
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def support(tt):
    return [k for k in range(4)
            if any(((tt >> r) ^ (tt >> (r ^ (1 << k)))) & 1 for r in range(16))]


def orbit(tt, row_maps):
    members = set()
    for row_map in row_maps:
        value = sum(((tt >> src) & 1) << dst for dst, src in enumerate(row_map))
        members.update((value, value ^ 65535))
    return members


def family():
    source = ROOT / ".local/abc/src/base/abci/abcMeasure.c"
    match = re.search(r"static unsigned u4VarTts\[222\]\s*=\s*\{([^}]+)\}", source.read_text())
    if match is None:
        raise ValueError("Missing the original ABC representative table")
    reps = [int(s, 16) for s in re.findall(r"0x[0-9A-Fa-f]+", match.group(1))]
    rows = []
    for perm in permutations(range(4)):
        unphased = [sum(((r >> p) & 1) << k for k, p in enumerate(perm)) for r in range(16)]
        rows.extend([[v ^ phase for v in unphased] for phase in range(16)])
    covered = set()
    active, boundary = [], []
    for truth in reps:
        members = orbit(truth, rows)
        assert covered.isdisjoint(members)
        covered.update(members)
        bits = support(truth)
        if len(bits) == 4:
            active.append(f"{truth:04x}")
        else:
            boundary.append(dict(truth=f"{truth:04x}", essential_inputs=bits))
    assert (len(reps), len(active), len(boundary), len(covered)) == (222, 208, 14, 65536)
    return dict(source="src/base/abci/abcMeasure.c:u4VarTts",
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                orbit_cover=len(covered), essential=active, boundary=boundary)


if __name__ == "__main__":
    print(json.dumps(family(), indent=2))
