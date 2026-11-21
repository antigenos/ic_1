"""Check NPN transport of actual four-input library circuits over every signed input permutation."""
import argparse
from collections import Counter
from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path

from library import check

FULL = 0xffff
INPUTS = tuple(sum(((r >> i) & 1) << r for r in range(16)) for i in range(4))
GATES = {2, 4, 6, 8, 14}


def apply(code, high, low):
    values = {2: low & ~high, 4: high & ~low, 6: high ^ low, 8: high & low, 14: high | low}
    return values[code]


def recode(code, high_phase, low_phase):
    phase = (high_phase << 1) | low_phase
    out_phase = (code >> phase) & 1
    new_code = sum((((code >> (k ^ phase)) & 1) ^ out_phase) << k for k in range(4))
    assert new_code in GATES
    return new_code, out_phase


def support(t):
    return all(any(((t >> r) ^ (t >> (r ^ (1 << i)))) & 1 for r in range(16)) for i in range(4))


def audit(data):
    assert check(data) == data["verified"]
    rows = [row for row in data["circuits"] if row["activity"] >= 0]
    owners = {}
    codes = {(c,h,l): recode(c,h,l) for c in GATES for h in range(2) for l in range(2)}
    maps = 0
    for perm in permutations(range(4)):
        initial = [INPUTS[p] for p in perm]
        for phase in range(16):
            maps += 1
            signs = [(phase >> i) & 1 for i in range(4)]
            source_rows = [phase ^ sum(((r >> p) & 1) << i for i,p in enumerate(perm)) for r in range(16)]
            assert sorted(source_rows) == list(range(16))
            for row in rows:
                bits = signs.copy()
                wires = initial.copy()
                score = 0
                for i,(high,low,op) in enumerate(row["gates"]):
                    actual, bit = codes[op,bits[high],bits[low]]
                    wire = apply(actual,wires[high],wires[low])
                    bits.append(bit)
                    wires.append(wire)
                    if i+1 < len(row["gates"]):
                        n = wire.bit_count()
                        score += 2*n*(16-n)
                source = int(row["truth"],16)
                target = sum(((source >> src) & 1) << r for r,src in enumerate(source_rows))
                recovered = wires[-1] ^ (FULL if bits[-1] ^ row["complement"] else 0)
                assert score == row["activity"] and recovered == target
                for equivalent in (target,target ^ FULL):
                    assert owners.setdefault(equivalent,row["truth"]) == row["truth"]
    domain = {t for t in range(65536) if support(t)}
    covered = set(owners)
    assert covered <= domain and len(domain) == 64594 and maps == 384
    if len(rows) == len(data["circuits"]):
        assert covered == domain
    digest = sha256("".join(f"{t:04x} {owners[t]}\n" for t in sorted(covered)).encode()).hexdigest()
    return dict(classes=len(rows), distinct_truth_tables=len(covered), full_support_domain=len(domain),
                signed_input_maps=maps, circuit_replays=len(rows)*maps,
                verified_output_phases=2*len(rows)*maps, table_sha256=digest,
                orbit_sizes=dict(sorted(Counter(owners.values()).items())))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("library",type=Path)
    parser.add_argument("output",type=Path)
    args = parser.parse_args()
    result = audit(json.loads(args.library.read_text()))
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(result["classes"], result["distinct_truth_tables"], result["circuit_replays"])
