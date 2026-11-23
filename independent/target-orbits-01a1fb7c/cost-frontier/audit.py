"""Reconstruct author-format circuits, run the independent simulator and cross-check historical optima."""
import argparse
from dataclasses import dataclass
from functools import cache
from itertools import combinations, permutations
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path.insert(0,str(STUDY/'reproduction/tools'))
from witness import simulate

N = 16
MASK = 65535
PINS = (0xaaaa, 0xcccc, 0xf0f0, 0xff00)
INF = 1000000
MAPS = []
for perm in permutations(range(4)):
    for phase in range(16):
        MAPS.append(tuple(sum(((x >> i) & 1) << j for i, j in enumerate(perm)) ^ phase
                          for x in range(16)))


def normal(t):
    return t ^ (MASK if t & 1 else 0)


def image(t, mapping):
    return normal(sum(((t >> y) & 1) << x for x, y in enumerate(mapping)))


@cache
def representative(t):
    return min(image(t, g) for g in MAPS)


def candidates(wires):
    for a, b in combinations(wires, 2):
        for code, signal in ((2, b & ~a), (4, a & ~b), (6, a ^ b), (8, a & b), (14, a | b)):
            yield signal, (a, b, code)


def rebuild(target, raw, state):
    mapping = next(g for g in MAPS if image(raw, g) == normal(target))
    pending = {image(t, mapping) for t in state}
    available = list(PINS)
    derivation = {}
    while pending:
        next_gates = {}
        for t, gate in candidates(available):
            if t in pending:
                next_gates.setdefault(t, gate)
        if not next_gates:
            raise ValueError('Unattainable witness prefix')
        derivation.update(next_gates)
        available.extend(next_gates)
        pending.difference_update(next_gates)
    gate = next(gate for t, gate in candidates(available) if t == normal(target))
    keep = set()
    def visit(t):
        if t in derivation and t not in keep:
            keep.add(t)
            a,b,_ = derivation[t]
            visit(a)
            visit(b)
    for t in gate[:2]:
        visit(t)
    names = {t: chr(97+i) for i, t in enumerate(PINS)}
    lines = []
    score = 0
    for t in available:
        if t in keep:
            a, b, code = derivation[t]
            index = len(names)
            lines.append(f"{index:02d} = 4'b{code:04b}( {names[a]} {names[b]} )")
            names[t] = f'{index:02d}'
            score += 2*t.bit_count()*(16-t.bit_count())
    a,b,code = gate
    code ^= 15 if target & 1 else 0
    lines.append(f"{len(names):02d} = 4'b{code:04b}( {names[a]} {names[b]} )")
    text = '\n'.join([f'Realization of given 4-input function using {len(lines)} two-input gates complementary={target & 1}:',
                      *reversed(lines), f'Switching Activity={score}'])
    return text, simulate(text, 4, target)


@dataclass
class Entry:
    upper: int
    lower: int
    uniform: int
    raw: int
    state: list


def read_table(path):
    rows = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if parts[0] == 'target':
            target, upper, lower, uniform, raw, *state = map(int, parts[1:])
            if target in rows:
                raise ValueError('duplicate representative')
            rows[target] = Entry(upper, lower, uniform, raw, state)
        elif parts[0] == 'meta':
            meta = dict(zip(('n','cap','states','edges','crossings','first_crossing'),map(int,parts[1:])))
    if meta['n'] != 4 or len(rows) != 222:
        raise ValueError('expected the entire four-input library')
    return meta, rows


def historical():
    known = {}
    for line in (STUDY/'evidence/full-300/runs.jsonl').read_text().splitlines():
        r = json.loads(line)
        w = r.get('witness')
        if w:
            assert simulate(r['solver_output'],4,int(w['truth'],16)) == w
            assert known.setdefault(w['truth'], w['activity']) == w['activity']
    return known


def audit(table):
    meta, rows = read_table(table)
    family = json.loads((STUDY/'reproduction/evidence/npn-family.json').read_text())['essential']
    known = historical()
    results = []
    for key in family:
        t = int(key,16)
        row = rows[representative(normal(t))]
        upper = None
        w = None
        if row.upper < INF:
            assert row.upper == sum(2*v.bit_count()*(16-v.bit_count()) for v in row.state)
            w, outcome = rebuild(t, row.raw, row.state)
            upper = outcome['activity']
            assert row.lower <= upper <= row.upper
        if key in known:
            assert row.lower <= known[key] <= (upper if upper is not None else INF) or (
                upper is not None and upper < known[key] and row.lower <= upper), (key,row,known[key],upper)
            # A cheaper witness contradicts an earlier exact result and needs investigation.
            assert upper is None or known[key] <= upper, (key,known[key],upper)
        results.append(dict(truth=key, lower=row.lower, uniform=row.uniform,
                            upper=upper, historical=known.get(key), circuit=w))
    return meta, results


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('table', type=Path)
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    meta, results = audit(args.table)
    extra = [r['truth'] for r in results if r['lower']==r['upper'] and r['upper']!=r['uniform']]
    summary = dict(meta, targets=len(results), historical=sum(r['historical'] is not None for r in results),
                   witnesses=sum(r['upper'] is not None for r in results),
                   uniform=sum(r['uniform']==r['upper'] for r in results),
                   certified=sum(r['lower']==r['upper'] for r in results),
                   strict_bounds=sum(r['lower']>r['uniform'] for r in results), extra=extra,
                   holdouts=[{k:r[k] for k in ('truth','lower','upper','historical')}
                             for r in results if r['truth'] in ('0017','018b')])
    if args.out:
        args.out.write_text(json.dumps(dict(summary=summary, targets=results),indent=2))
    print(json.dumps(summary))
