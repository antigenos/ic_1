"""Counterfactual explanation replay and out-of-fold algorithm selection."""
from collections import Counter
import hashlib
import json
import time
from pathlib import Path
from audit_trail import audit, variable_map

ROOT = Path(__file__).resolve().parents[1]


def explanations(path):
    groups = {"count":[], "sel":[]}
    for line in path.read_text().splitlines():
        if line.startswith("REASON "):
            tokens = line.split()
            kind = "count" if tokens[7] == "-1" else "sel"
            groups[kind].append(tokens)
    result = {}
    for kind, group in groups.items():
        rows = []
        start = time.perf_counter()
        for i in range(min(32,len(group))):
            tokens = group[round(i*(len(group)-1)/31)]
            vm = variable_map(*map(int,tokens[1:3]))
            initial = len(tokens) - 8
            assert audit(" ".join(tokens)) == kind
            kept = list(tokens)
            calls = 0
            for lit in tokens[9:]:
                if vm[int(lit)>>1][0] == "sel":
                    continue
                new = list(kept)
                idx = new.index(lit,9)
                new.pop(idx)
                calls += 1
                try:
                    audit(" ".join(new))
                except AssertionError as exc:
                    if not exc.args or not isinstance(exc.args[0],tuple) or exc.args[0][0] != "satisfiable reason":
                        raise
                else:
                    kept = new
            assert audit(" ".join(kept)) == kind
            rows.append(dict(before=initial, after=len(kept)-8, oracle_calls=calls))
        result[kind] = dict(population=len(group), sample=len(rows),
                            before=sum(r["before"] for r in rows), after=sum(r["after"] for r in rows),
                            shorter=sum(r["after"]<r["before"] for r in rows),
                            total_calls=sum(r["oracle_calls"] for r in rows),
                            wall_s=time.perf_counter()-start, rows=rows)
    return result


def signature(text):
    truth = int(text,16)
    ones = truth.bit_count()
    diffs, counts = [], []
    for bit in range(4):
        low = [r for r in range(16) if not r >> bit & 1]
        a = sum(truth >> r & 1 for r in low)
        b = ones-a
        diffs.append(sum(((truth>>r) ^ (truth>>(r ^ 1<<bit))) & 1 for r in low))
        counts.append(tuple(sorted((min(a,8-a),min(b,8-b)))))
    return (min(ones,16-ones), *sorted(diffs), *(v for pair in sorted(counts) for v in pair))


def portfolio():
    roles = ("both","support")
    data = {}
    for role in roles:
        for line in (ROOT/f"evidence/e14-main/{role}.jsonl").read_text().splitlines():
            r=json.loads(line)
            data.setdefault(r["experiment"]["truth"],{})[role]=r
    ft = {x:signature(x) for x in data}
    fold = {x:int(hashlib.sha256(x.encode()).hexdigest(),16)%5 for x in data}
    def cost(x,m):
        return data[x][m]["capped_wall_s"]
    def distance(x,y):
        return sum((a-b)**2 for a,b in zip(ft[x],ft[y]))
    rows=[]
    for x in sorted(data):
        peers=sorted((y for y in data if fold[y]!=fold[x]),key=lambda y:(distance(x,y),y))[:7]
        pick=min(roles,key=lambda m:sum(cost(y,m) for y in peers))
        best=min(roles,key=lambda m:cost(x,m))
        rows.append(dict(truth=x, fold=fold[x], chosen=pick, oracle=best, peers=peers))
    def aggregate(choices):
        return dict(capped_s=sum(cost(r["truth"],m) for r,m in zip(rows,choices)),
                    solved=sum("witness" in data[r["truth"]][m] for r,m in zip(rows,choices)))
    return dict(n=len(rows), selected=dict(Counter(r["chosen"] for r in rows)),
                baseline=aggregate(["both"]*len(rows)), selected_out_of_fold=aggregate([r["chosen"] for r in rows]),
                oracle_upper_bound=aggregate([r["oracle"] for r in rows]),rows=rows)


if __name__=="__main__":
    print(json.dumps(dict(explanations=explanations(ROOT/".local/e11j-both/0189/solver.log"),
                          portfolio=portfolio()),indent=2))
