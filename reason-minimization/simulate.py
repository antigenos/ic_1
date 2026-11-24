"""Check the unary projection independently before solver integration."""
import gzip
import json
import sys
from pathlib import Path
from itertools import product
D = Path(__file__).resolve().parent
sys.path.insert(0, str(D.parent / "tools"))
from audit_trail import audit, variable_map
from screen_offline import explanations

def projected(rows, ones, zeros, a):
    return any(ones <= m <= rows-zeros for m in (a, rows-a))

def check():
    tests = 0
    for rows in (4, 8):
        for mask in product((-1, 0, 1), repeat=rows):
            ones, zeros = mask.count(1), mask.count(0)
            filled = {min(m, rows-m) for bits in product((0, 1), repeat=rows-ones-zeros)
                      for m in [ones + sum(bits)]}
            for a in range(1, rows//2+1):
                assert (a in filled) == projected(rows, ones, zeros, a)
                tests += 1
    src = D.parent / "evidence/screen-traces/frozen-0189.log.gz"
    old = explanations(src)
    hist = json.loads((D.parent/"evidence/screen-offline.json").read_text())["explanations"]
    for k in old:
        assert old[k]["rows"] == hist[k]["rows"]
    groups = {"count": [], "sel": []}
    for line in gzip.open(src, "rt"):
        if line.startswith("REASON "):
            groups["count" if line.split()[7]=="-1" else "sel"].append(line)
    examples = {}
    for k, lines in groups.items():
        stats = []
        for i in range(32):
            f = lines[round(i*(len(lines)-1)/31)].split()
            table = variable_map(*map(int, f[1:3]))
            lits = list(map(int, f[8:]))
            victim = table[lits[0]>>1]
            ends = set(map(int, f[5:7]))
            rows = 1 << int(f[1])
            fixed = {j:[1,0] for j in ends}
            for lit in lits[1:]:
                key = table[lit>>1]
                if key[0]=="row":
                    fixed[key[1]][lit&1] += 1
            kept = [lits[0]]
            for lit in lits[1:]:
                key = table[lit>>1]
                if key[0]=="count" and key[1] in ends:
                    obj, a = key[1:]
                    z,o = fixed[obj]
                    if victim[:2]==("count",obj) or not projected(rows,o,z,a):
                        continue
                kept.append(lit)
            assert audit(" ".join(f[:8]+list(map(str,kept)))) == k
            stats.append([len(lits),len(kept)])
        examples[k] = stats
    return dict(exact_projection_checks=tests, historical_oracle_rows_equal=True, samples=examples)

if __name__=="__main__":
    print(json.dumps(check(), indent=2))
