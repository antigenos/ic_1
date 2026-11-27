"""Check cross-method agreement, independent cost intervals and every cold proof handoff."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from zipfile import ZipFile

from family import HERE, write_once
from witness import simulate


def records(blob):
    return [json.loads(line) for line in blob.splitlines()]


def datasets(full):
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as archive:
        for name, configs in (("e14-main",("author","support","both")),
                              ("e14-ablation",("off","counts","early","nobudget","both"))):
            yield name, [row for method in configs for row in records(archive.read(f"evidence/{name}/{method}.jsonl"))]
    yield "confirmation", [row for file in sorted((HERE/"confirmation").glob("confirm-*.jsonl"))
                           for row in records(file.read_bytes())]
    for name in (("proof-confirm","family-208","proof-full") if full else ("proof-confirm",)):
        folder = HERE/name
        stream = (folder/"runs.jsonl").read_bytes().replace(b"\r\n",b"\n")
        assert sha256(stream).hexdigest() == json.loads((folder/"summary.json").read_bytes())["raw_sha256"]
        yield name, records(stream)


def write_case_table(path, cases, intervals, witnessed):
    # Distinct names preserve the two runs of the reconstructed method and the
    # same-binary control. Only within-batch comparisons share their protocol.
    arms = ("author","support","both","F","H","N","3","5")
    columns = ["truth","independent_lower","independent_upper","returned_activity"]
    for arm in arms:
        columns.extend([arm+"_status",arm+"_capped_s"])
    rows = [columns]
    assert set(cases) == set(intervals)
    for truth, (lower,upper) in sorted(intervals.items()):
        assert set(cases[truth]) == set(arms)
        solved = any(status=="completed" for status,_ in cases[truth].values())
        fields = ["0x"+truth,str(lower),str(upper),str(witnessed[truth]) if solved else ""]
        for arm in arms:
            fields.extend(cases[truth][arm])
        rows.append(fields)
    text = "".join("\t".join(row)+"\n" for row in rows)
    if path.exists():
        assert path.read_text(encoding="utf-8") == text, "Existing case table differs"
    else:
        write_once(path,text.encode("utf-8"))


def audit(full,case_table=None):
    if case_table is not None and not full:
        raise ValueError("The case table requires both full censuses")
    limits = (302,366,440,500,560)
    tables = {cap:json.loads((HERE/f"{'closure' if cap==366 else 'prefix'}-{cap}.json").read_bytes())
              for cap in limits}
    exact = tables[560]["certificates"]
    upper = json.loads((HERE/"formula-720.json").read_bytes())["cases"]
    intervals = {t:([v,v] if v is not None else upper[t]["dag_interval"]) for t,v in exact.items()}
    assert len(intervals)==208 and all(lo<=hi for lo,hi in intervals.values())
    groups = {}
    witnessed = {}
    cases = {}
    states = {cap:set() for cap in limits}
    required = {"e14-main":624,"e14-ablation":15,"confirmation":48,"proof-confirm":24,"family-208":624,"proof-full":416}
    for name,rows in datasets(full):
        assert len(rows)==required[name]
        count = independent = checkpoints = 0
        pairs = set()
        for row in rows:
            exp = row["experiment"]
            t = exp["truth"]
            arm = exp.get("method",exp.get("arm"))
            assert t in intervals and arm is not None and (t,arm) not in pairs
            pairs.add((t,arm))
            text = row["solver_output"]
            assert sha256(text.encode()).hexdigest()==row["solver_log_sha256"]
            if "witness" in row:
                assert row["status"]=="solver_completed_verified_witness"
                w = simulate(text,4,int(t,16))
                assert w==row["witness"]
                lo,hi = intervals[t]
                assert lo <= w["activity"] <= hi
                assert witnessed.setdefault(t,w["activity"])==w["activity"]
                independent += w["activity"]==lo
                count += 1
            else:
                assert row["status"]=="timeout"
            if case_table is not None and name in ("e14-main","family-208","proof-full"):
                entries = cases.setdefault(t,{})
                assert arm not in entries
                assert row["timeout_s"]==300 and row["capped_wall_s"]==min(row["wall_s"],300)
                entries[arm] = ("completed" if "witness" in row else "timeout",str(row["capped_wall_s"]))
            if name not in ("proof-full","proof-confirm"):
                continue
            if arm=="3":
                assert "PREFIX " not in text
                continue
            assert arm=="5"
            log = text.replace("\r","")
            steps = [tuple(map(int,x)) for x in re.findall(r"^PREFIX cap=(\d+) states=(\d+) score=(-?\d+)$",log,re.M)]
            assert [c for c,_,_ in steps]==list(limits[:len(steps)])
            bound = 0
            for i,(cap,n,score) in enumerate(steps):
                expected = tables[cap]["certificates"][t]
                assert score==(-1 if expected is None else expected)
                assert n>0 and (cap==366 or n==tables[cap]["states"])
                states[cap].add(n)
                assert score<0 or i==len(steps)-1
                bound = cap+2 if score<0 else score
                checkpoints += 1
            for raw in re.findall(r"^PREFIX author_search_from=(\d+)$",log,re.M):
                assert int(raw)==bound
            for raw in re.findall(r"^PREFIX author_verified=pins cost=(\d+) gates=\d+$",log,re.M):
                assert steps and int(raw)==steps[-1][2]==exact[t]
        groups[name]=dict(runs=len(rows),witness_rows=count,independently_proved_witness_rows=independent,
                          checked_completed_prefix_enumerations=checkpoints)
    assert all(len(v)<=1 for v in states.values())
    if case_table is not None:
        write_case_table(case_table,cases,intervals,witnessed)
    return dict(groups=groups,independent_intervals=len(intervals),distinct_solver_values=len(witnessed),
                distinct_solver_values_equal_independent_lower=sum(v==intervals[t][0] for t,v in witnessed.items()),
                solver_values_with_open_independent_interval={t:v for t,v in sorted(witnessed.items()) if v!=intervals[t][0]},
                observed_prefix_state_counts={str(c):sorted(v) for c,v in states.items()})


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--through-confirmation",action="store_true")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--case-table",type=Path,help="Export or verify the aligned 208-function full-census table")
    args = parser.parse_args()
    if args.case_table is not None and args.through_confirmation:
        parser.error("--case-table requires the full audit")
    report = audit(not args.through_confirmation,args.case_table)
    if args.output:
        write_once(args.output,(json.dumps(report,indent=2)+"\n").encode())
    print(json.dumps(report,ensure_ascii=False))
