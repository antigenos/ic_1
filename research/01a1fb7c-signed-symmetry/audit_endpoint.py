"""Independently decode the target/first/last incompatibilities emitted in C."""
from argparse import ArgumentParser
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from check_chain import least_rank,rank
from check_symmetry import FIRST,HERE,OPS,PINS,gate
from endpoint import endpoint_bound


def check(include):
    with ZipFile(HERE/"date-tcjap-reproduction.zip") as z:
        targets=[int(t,16) for t in json.loads(z.read("evidence/npn-family.json"))["essential"]]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        if include is None:
            include=root
            for lib,header in (("restriction","restriction_table"),("endpoint","endpoint_table")):
                subprocess.run([sys.executable,str(HERE/(lib+".py")),"--header",str(root/(header+".h"))],check=True)
        exe=root/("probe.exe" if os.name=="nt" else "probe")
        subprocess.run(["gcc","-O2","-std=c11","-I",str(include),str(HERE/"endpoint_probe.c"),"-o",str(exe)],check=True)
        def trace(requests,mode):
            return subprocess.check_output([str(exe)],text=True,
                env={**os.environ,"REPLAY_FIRST_SYMMETRY":"chain-first","REPLAY_ENDPOINT":mode},
                input="".join(f"{t:04x} {n} {b}\n" for t,n,b in requests)).splitlines()
        lines=iter(trace([(t,2,-1) for t in targets],"joint"))
        cells=0
        for t in targets:
            assert next(lines)==f"T {t:04x}"
            reps={g for g in FIRST if rank(g)==least_rank(t,g)}
            for _ in range(len(reps)):
                label,key,*values=next(lines).split()
                g=int(key,16)
                assert label=="G" and g in reps
                reps.remove(g)
                assert list(map(int,values))==[endpoint_bound(t,g,k,op) for k in range(5) for op in OPS]
                cells+=len(values)
            assert not reps
        assert next(lines,None) is None
        queries=[]
        cases=[]
        legal_rows=[]
        for t in (0x0189,0x03dd):
            for n in range(2,9):
                k=min(4,n-2)
                first={}
                last={op:tuple(2*(1+3*(n-1)+j)+(op>>(1+j)&1) for j in range(3)) for op in OPS}
                for hi in range(1,4):
                    for lo in range(hi):
                        for op in OPS:
                            g=gate(op,PINS[lo],PINS[hi])
                            if rank(g)==least_rank(t,g):
                                first[g]=(2*(1+3*n+hi)+1,2*(5+3*n+lo)+1,*(2*i+(op>>i&1) for i in range(1,4)))
                weights={(g,op):endpoint_bound(t,g,k,op) for g in first for op in OPS}
                cuts=set(weights.values())
                for b in sorted(cuts|{v-1 for v in cuts}):
                    ok={(g,op) for (g,op),v in weights.items() if v<=b}
                    gs={g for g,_ in ok}
                    ops={op for _,op in ok}
                    independent=Counter([first[g] for g in first.keys()-gs]+[last[o] for o in last.keys()-ops]) if ok else Counter()
                    extra=Counter(first[g]+last[o] for g in gs for o in ops if (g,o) not in ok)
                    queries.append((t,n,b))
                    cases.append((bool(ok),independent,extra))
                    legal_rows.append([(frozenset(first[g]+last[o]),(g,o) in ok) for g,o in weights])
        totals={}
        for mode in ("margins","joint"):
            lines=iter(trace(queries,mode))
            nclauses=0
            for (t,n,b),(ok,single,extra) in zip(queries,cases):
                assert next(lines)==f"Q {t:04x} {n} {b}" and next(lines)==f"P {int(ok)}"
                expected=single+extra if mode=="joint" else single
                actual=Counter()
                for _ in range(expected.total()):
                    label,*lits=next(lines).split()
                    assert label=="C"
                    actual[tuple(map(int,lits))]+=1
                assert expected==actual
                nclauses+=expected.total()
            assert next(lines,None) is None
            totals[mode]=nclauses
        output=trace(queries,"short")
        cursor=0
        sizes=Counter()
        checked=0
        for (t,n,b),(passed,_,_),choices in zip(queries,cases,legal_rows):
            assert output[cursor:cursor+2]==[f"Q {t:04x} {n} {b}",f"P {int(passed)}"]
            cursor+=2
            clauses=[]
            while cursor<len(output) and output[cursor].startswith("C "):
                lits=frozenset(map(int,output[cursor].split()[1:]))
                assert 1<=len(lits)<=8
                sizes[len(lits)]+=1
                clauses.append(lits)
                cursor+=1
            for bits,allowed in choices:
                assert (passed and not any(c<=bits for c in clauses))==allowed
                checked+=1
        assert cursor==len(output)
    return dict(targets=len(targets),matched_bound_cells=cells,windows_per_mode=len(queries),matched_clauses=totals,
                compact_validated_assignments=checked,compact_clause_lengths=dict(sorted(sizes.items())))


if __name__=="__main__":
    p=ArgumentParser()
    p.add_argument("--include",type=Path)
    print(json.dumps(check(p.parse_args().include),indent=2))
