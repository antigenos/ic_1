"""Compare the emitted BDD histogram indices with the original mixed-radix specification."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("library",type=Path)
    p.add_argument("binary",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args()
    circuits=json.loads(args.library.read_text())["circuits"]
    windows=sorted({(len(c["gates"])-1,c["activity"]) for c in circuits if c["activity"]>=0})
    requests="\n".join(f"{g} {s}" for g,s in windows)
    reply=subprocess.run([str(args.binary.resolve())],input=requests,capture_output=True,text=True,check=True)
    actual={}
    for line in reply.stdout.splitlines():
        gates,score,*keys=map(int,line.split())
        actual[gates,score]=keys
    assert list(actual)==windows
    expected={w:[] for w in windows}
    weights=[2*k*(16-k) for k in range(1,9)]
    for gates in sorted({g for g,_ in windows}):
        digits=[(gates+1)**i for i in range(8)]
        for entries in itertools.combinations_with_replacement(range(8),gates):
            cost=sum(weights[i] for i in entries)
            if (gates,cost) in expected:
                expected[gates,cost].append(sum(digits[i] for i in entries))
    for w in windows:
        assert sorted(expected[w])==actual[w] and actual[w],w
    report=dict(windows=len(windows),histograms=sum(map(len,actual.values())),
                ordered_index_sha256=hashlib.sha256(reply.stdout.encode()).hexdigest(),
                entries=[dict(paid_gates=g,activity=s,original_indices=actual[g,s]) for g,s in windows])
    args.output.write_text(json.dumps(report,separators=(",",":"))+"\n")
    print(report["windows"],report["histograms"])
